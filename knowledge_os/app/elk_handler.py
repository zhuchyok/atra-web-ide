"""
ELK Handler для отправки логов в Elasticsearch
Интеграция централизованного логирования с ELK стеком
"""
import asyncio
import httpx
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ELKHandler(logging.Handler):
    """Handler для отправки логов в Elasticsearch"""
    
    def __init__(
        self,
        elasticsearch_url: str = "http://atra-elasticsearch:9200",
        index_prefix: str = "atra-logs",
        batch_size: int = 10,
        flush_interval: float = 5.0
    ):
        """
        Args:
            elasticsearch_url: URL Elasticsearch сервера
            index_prefix: Префикс для индексов (будет создан индекс atra-logs-YYYY.MM.DD)
            batch_size: Размер батча для отправки
            flush_interval: Интервал отправки батча в секундах
        """
        super().__init__()
        self.elasticsearch_url = elasticsearch_url
        self.index_prefix = index_prefix
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.client: Optional[httpx.AsyncClient] = None
        self._log_buffer: list[Dict[str, Any]] = []
        self._last_flush = datetime.now()
        self._init_client()
        self._start_background_flusher()
    
    def _init_client(self):
        """Инициализация HTTP клиента"""
        try:
            self.client = httpx.AsyncClient(
                timeout=5.0,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        except Exception as e:
            logger.error(f"Failed to init ELK client: {e}")
    
    def emit(self, record: logging.LogRecord):
        """Отправка лога в буфер (асинхронная отправка в фоне)"""
        if not self.client:
            return
        
        try:
            # Формируем структурированный лог
            log_data = {
                "@timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
                "pathname": record.pathname,
            }
            
            # Добавляем дополнительные поля если есть
            if hasattr(record, 'extra') and record.extra:
                log_data.update(record.extra)
            
            # Добавляем exception если есть
            if record.exc_info:
                import traceback
                log_data["exception"] = traceback.format_exception(*record.exc_info)
            
            # Добавляем в буфер
            self._log_buffer.append(log_data)
            
            # Отправляем если буфер заполнен
            if len(self._log_buffer) >= self.batch_size:
                asyncio.create_task(self._flush_buffer())
        except Exception:
            self.handleError(record)
    
    def _start_background_flusher(self):
        """Запуск фонового процесса для периодической отправки логов"""
        async def flush_loop():
            while True:
                try:
                    await asyncio.sleep(self.flush_interval)
                    if self._log_buffer:
                        await self._flush_buffer()
                except Exception as e:
                    logger.debug(f"Error in ELK flush loop: {e}")
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(flush_loop())
            else:
                # Если нет event loop, создаем в отдельном потоке
                import threading
                def run_loop():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    new_loop.run_until_complete(flush_loop())
                
                thread = threading.Thread(target=run_loop, daemon=True)
                thread.start()
        except Exception as e:
            logger.debug(f"Failed to start ELK flush loop: {e}")
    
    async def _flush_buffer(self):
        """Отправка накопленных логов в Elasticsearch"""
        if not self.client or not self._log_buffer:
            return
        
        # Копируем буфер и очищаем
        logs_to_send = self._log_buffer.copy()
        self._log_buffer.clear()
        self._last_flush = datetime.now()
        
        if not logs_to_send:
            return
        
        try:
            # Создаем индекс для сегодняшней даты
            index_name = f"{self.index_prefix}-{datetime.now(timezone.utc).strftime('%Y.%m.%d')}"
            
            # Отправляем через bulk API для эффективности
            bulk_body = []
            for log_data in logs_to_send:
                # Bulk API формат: action + data
                bulk_body.append(json.dumps({"index": {}}))
                bulk_body.append(json.dumps(log_data))
            
            url = f"{self.elasticsearch_url}/{index_name}/_bulk"
            response = await self.client.post(
                url,
                content="\n".join(bulk_body) + "\n",
                headers={"Content-Type": "application/x-ndjson"}
            )
            response.raise_for_status()
            
            logger.debug(f"✅ Sent {len(logs_to_send)} logs to Elasticsearch")
        except httpx.HTTPError as e:
            logger.debug(f"Failed to send logs to Elasticsearch: {e}")
            # Возвращаем логи в буфер при ошибке (ограничиваем размер)
            if len(self._log_buffer) < self.batch_size * 2:
                self._log_buffer = logs_to_send + self._log_buffer
        except Exception as e:
            logger.debug(f"Unexpected error sending logs to Elasticsearch: {e}")
    
    def flush(self):
        """Синхронный flush (для совместимости с logging.Handler)"""
        if self._log_buffer:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Если loop уже запущен, создаем задачу
                    asyncio.create_task(self._flush_buffer())
                else:
                    # Если loop не запущен, запускаем
                    loop.run_until_complete(self._flush_buffer())
            except RuntimeError:
                # Нет event loop, создаем новый
                asyncio.run(self._flush_buffer())
    
    def close(self):
        """Закрытие клиента и отправка оставшихся логов"""
        if self._log_buffer:
            self.flush()
        
        if self.client:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.client.aclose())
                else:
                    loop.run_until_complete(self.client.aclose())
            except Exception:
                pass
        
        super().close()


def create_elk_handler(
    elasticsearch_url: Optional[str] = None,
    index_prefix: str = "atra-logs",
    log_level: int = logging.INFO
) -> Optional[ELKHandler]:
    """
    Создает и настраивает ELK handler
    
    Args:
        elasticsearch_url: URL Elasticsearch (по умолчанию из переменной окружения)
        index_prefix: Префикс для индексов
        log_level: Уровень логирования
    
    Returns:
        ELKHandler или None если не удалось создать
    """
    import os
    
    if elasticsearch_url is None:
        elasticsearch_url = os.getenv("ELASTICSEARCH_URL", "http://atra-elasticsearch:9200")
    
    # Проверяем, включен ли ELK
    use_elk = os.getenv("USE_ELK", "false").lower() in ("true", "1", "yes")
    if not use_elk:
        return None
    
    try:
        handler = ELKHandler(
            elasticsearch_url=elasticsearch_url,
            index_prefix=index_prefix
        )
        handler.setLevel(log_level)
        return handler
    except Exception as e:
        logger.warning(f"Failed to create ELK handler: {e}")
        return None
