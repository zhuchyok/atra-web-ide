"""
Write queue для сериализации записей в SQLite БД.

Обеспечивает последовательную обработку записей от разных агентов,
устраняя блокировки БД при конкурентных записях.
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class WriteOperationType(Enum):
    """Типы операций записи"""
    EXECUTE = "execute"
    EXECUTEMANY = "executemany"
    COMMIT = "commit"


@dataclass
class WriteOperation:
    """Операция записи в очередь"""
    operation_type: WriteOperationType
    query: str
    params: Any = None
    is_write: bool = True
    timestamp: float = None
    operation_id: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.operation_id is None:
            self.operation_id = f"op_{int(self.timestamp * 1000000)}"


@dataclass
class WriteMetrics:
    """Метрики производительности write queue"""
    total_operations: int = 0
    completed_operations: int = 0
    failed_operations: int = 0
    total_latency: float = 0.0
    max_latency: float = 0.0
    min_latency: float = float('inf')
    queue_size: int = 0
    queue_max_size: int = 0
    
    def add_operation(self, latency: float):
        """Добавить метрику операции"""
        self.total_operations += 1
        self.completed_operations += 1
        self.total_latency += latency
        self.max_latency = max(self.max_latency, latency)
        self.min_latency = min(self.min_latency, latency)
    
    def add_failure(self):
        """Добавить метрику неудачной операции"""
        self.total_operations += 1
        self.failed_operations += 1
    
    def get_avg_latency(self) -> float:
        """Получить среднюю задержку"""
        if self.completed_operations == 0:
            return 0.0
        return self.total_latency / self.completed_operations
    
    def get_p95_latency(self, latencies: deque) -> float:
        """Получить 95-й перцентиль задержки"""
        if len(latencies) == 0:
            return 0.0
        sorted_latencies = sorted(latencies)
        p95_index = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[p95_index] if p95_index < len(sorted_latencies) else sorted_latencies[-1]


class DatabaseWriteQueue:
    """Очередь для сериализации записей в БД"""
    
    def __init__(
        self,
        db_executor: Callable,
        max_retries: int = 5,
        initial_retry_delay: float = 0.5,
        max_queue_size: int = 1000,
        enable_metrics: bool = True,
    ):
        """
        Args:
            db_executor: Функция для выполнения SQL запросов
            max_retries: Максимальное количество попыток при ошибке
            initial_retry_delay: Начальная задержка между попытками (секунды)
            max_queue_size: Максимальный размер очереди
            enable_metrics: Включить сбор метрик
        """
        self.db_executor = db_executor
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.max_queue_size = max_queue_size
        self.enable_metrics = enable_metrics
        
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.worker_task: Optional[asyncio.Task] = None
        self.is_running = False
        self.metrics = WriteMetrics()
        self.latency_history: deque = deque(maxlen=1000)  # Храним последние 1000 операций
        
        # Lock для синхронных операций
        self._lock = asyncio.Lock()
    
    async def start(self):
        """Запустить worker для обработки очереди"""
        if self.is_running:
            logger.warning("⚠️ [WriteQueue] Worker уже запущен")
            return
        
        self.is_running = True
        self.worker_task = asyncio.create_task(self._worker())
        logger.info("✅ [WriteQueue] Worker запущен")
    
    async def stop(self, timeout: float = 10.0):
        """Остановить worker"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Ждем завершения обработки очереди
        if self.worker_task:
            try:
                await asyncio.wait_for(self.worker_task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("⚠️ [WriteQueue] Timeout при остановке worker")
                self.worker_task.cancel()
        
        logger.info("✅ [WriteQueue] Worker остановлен")
    
    async def execute(
        self,
        query: str,
        params: Any = None,
        is_write: bool = True,
        operation_type: WriteOperationType = WriteOperationType.EXECUTE,
    ) -> Any:
        """
        Добавить операцию в очередь и дождаться результата
        
        Args:
            query: SQL запрос
            params: Параметры запроса
            is_write: Является ли операция записью
            operation_type: Тип операции
            
        Returns:
            Результат выполнения запроса
        """
        operation = WriteOperation(
            operation_type=operation_type,
            query=query,
            params=params,
            is_write=is_write,
        )
        
        # Проверяем размер очереди
        if self.queue.qsize() >= self.max_queue_size:
            logger.warning(
                f"⚠️ [WriteQueue] Очередь переполнена ({self.queue.qsize()}/{self.max_queue_size})"
            )
        
        # Создаем Future для получения результата
        future = asyncio.Future()
        
        try:
            await self.queue.put((operation, future))
            
            # Обновляем метрики размера очереди
            if self.enable_metrics:
                async with self._lock:
                    self.metrics.queue_size = self.queue.qsize()
                    self.metrics.queue_max_size = max(
                        self.metrics.queue_max_size,
                        self.queue.qsize()
                    )
            
            # Ждем результат
            result = await future
            
            return result
            
        except asyncio.QueueFull:
            logger.error("❌ [WriteQueue] Очередь переполнена, операция отклонена")
            future.set_exception(RuntimeError("Write queue is full"))
            raise
    
    async def _worker(self):
        """Worker для обработки операций из очереди"""
        logger.info("🔄 [WriteQueue] Worker начал работу")
        
        while self.is_running:
            try:
                # Получаем операцию из очереди с таймаутом
                try:
                    operation, future = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Выполняем операцию
                start_time = time.time()
                result = await self._execute_operation(operation)
                latency = time.time() - start_time
                
                # Обновляем метрики
                if self.enable_metrics:
                    async with self._lock:
                        self.metrics.add_operation(latency)
                        self.latency_history.append(latency)
                
                # Устанавливаем результат
                if not future.done():
                    future.set_result(result)
                
                # Отмечаем задачу как выполненную
                self.queue.task_done()
                
            except asyncio.CancelledError:
                logger.info("🛑 [WriteQueue] Worker получил сигнал отмены")
                break
            except Exception as e:
                logger.error(f"❌ [WriteQueue] Ошибка в worker: {e}", exc_info=True)
                # Устанавливаем ошибку в future
                if 'future' in locals() and not future.done():
                    future.set_exception(e)
                if self.enable_metrics:
                    async with self._lock:
                        self.metrics.add_failure()
        
        logger.info("✅ [WriteQueue] Worker завершил работу")
    
    async def _execute_operation(self, operation: WriteOperation) -> Any:
        """Выполнить операцию с retry logic"""
        retry_delay = self.initial_retry_delay
        
        for attempt in range(self.max_retries):
            try:
                # Выполняем операцию через db_executor
                if operation.operation_type == WriteOperationType.EXECUTE:
                    result = await asyncio.to_thread(
                        self.db_executor,
                        operation.query,
                        operation.params,
                        operation.is_write
                    )
                elif operation.operation_type == WriteOperationType.EXECUTEMANY:
                    result = await asyncio.to_thread(
                        self.db_executor,
                        operation.query,
                        operation.params,
                        operation.is_write,
                        executemany=True
                    )
                else:
                    result = await asyncio.to_thread(
                        self.db_executor,
                        operation.query,
                        operation.params,
                        operation.is_write
                    )
                
                return result
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Проверяем, является ли ошибка временной (блокировка)
                if "locked" in error_str and attempt < self.max_retries - 1:
                    logger.warning(
                        f"⚠️ [WriteQueue] БД заблокирована "
                        f"(попытка {attempt+1}/{self.max_retries}), "
                        f"ждем {retry_delay}с..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                
                # Критическая ошибка или последняя попытка
                logger.error(
                    f"❌ [WriteQueue] Ошибка выполнения операции "
                    f"после {attempt+1} попыток: {e}"
                )
                raise
        
        # Если дошли сюда, все попытки исчерпаны
        raise RuntimeError(f"Не удалось выполнить операцию после {self.max_retries} попыток")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получить метрики производительности"""
        if not self.enable_metrics:
            return {}
        
        p95_latency = self.metrics.get_p95_latency(self.latency_history)
        
        return {
            "total_operations": self.metrics.total_operations,
            "completed_operations": self.metrics.completed_operations,
            "failed_operations": self.metrics.failed_operations,
            "avg_latency_ms": self.metrics.get_avg_latency() * 1000,
            "min_latency_ms": self.metrics.min_latency * 1000 if self.metrics.min_latency != float('inf') else 0,
            "max_latency_ms": self.metrics.max_latency * 1000,
            "p95_latency_ms": p95_latency * 1000,
            "queue_size": self.metrics.queue_size,
            "queue_max_size": self.metrics.queue_max_size,
            "success_rate": (
                self.metrics.completed_operations / self.metrics.total_operations
                if self.metrics.total_operations > 0
                else 0.0
            ),
        }
    
    def reset_metrics(self):
        """Сбросить метрики"""
        self.metrics = WriteMetrics()
        self.latency_history.clear()


# Singleton экземпляр write queue
_write_queue_instance: Optional[DatabaseWriteQueue] = None
_write_queue_lock = asyncio.Lock()


async def get_write_queue(
    db_executor: Optional[Callable] = None,
    **kwargs
) -> DatabaseWriteQueue:
    """Получить singleton экземпляр write queue"""
    global _write_queue_instance
    
    async with _write_queue_lock:
        if _write_queue_instance is None:
            if db_executor is None:
                raise ValueError("db_executor required for first initialization")
            _write_queue_instance = DatabaseWriteQueue(db_executor, **kwargs)
            await _write_queue_instance.start()
        
        return _write_queue_instance


async def shutdown_write_queue():
    """Остановить write queue"""
    global _write_queue_instance
    
    async with _write_queue_lock:
        if _write_queue_instance is not None:
            await _write_queue_instance.stop()
            _write_queue_instance = None

