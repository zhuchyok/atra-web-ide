"""
MLX Request Queue - Очередь запросов с приоритетами для MLX API Server
Решает проблему конкуренции между чатом с Викторией и Task Distribution
"""

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class RequestPriority(Enum):
    """Приоритеты запросов"""

    HIGH = 1  # Чат с Викторией (пользователь ждет ответа)
    MEDIUM = 2  # Task Distribution (может подождать)
    LOW = 3  # Фоновые задачи


@dataclass(order=True)
class QueuedRequest:
    """Запрос в очереди"""

    priority: RequestPriority = field(compare=True)
    created_at: datetime = field(compare=True)
    request_id: str = field(compare=False)
    callback: Callable = field(compare=False, default=None)
    timeout: float = field(compare=False, default=300.0)
    metadata: Dict[str, Any] = field(compare=False, default_factory=dict)

    def is_expired(self) -> bool:
        """Проверить, истек ли таймаут"""
        elapsed = (datetime.now() - self.created_at).total_seconds()
        return elapsed > self.timeout


class MLXRequestQueue:
    """
    Очередь запросов с приоритетами для MLX API Server

    Обеспечивает:
    - Приоритетную обработку чатов (HIGH)
    - Очередь для Task Distribution (MEDIUM)
    - Защиту от перегрузки
    - Таймауты для защиты от зависших запросов
    """

    def __init__(self, max_concurrent: int = 1, max_queue_size: int = 50):
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size
        self.active_requests = 0
        self.queue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._lock = asyncio.Lock()
        self._processing = False
        self._stats = {
            "total_queued": 0,
            "total_processed": 0,
            "total_expired": 0,
            "total_rejected": 0,
            "by_priority": {p: 0 for p in RequestPriority},
        }

    async def add_request(
        self,
        priority: RequestPriority,
        callback: Callable,
        timeout: float = 300.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> tuple[bool, Optional[str], Optional[int]]:
        """
        Добавить запрос в очередь

        Args:
            priority: Приоритет запроса
            callback: Асинхронная функция для выполнения (должна быть awaitable)
            timeout: Таймаут в секундах
            metadata: Дополнительные метаданные

        Returns:
            (success, request_id, queue_position)
            - success: Успешно добавлен в очередь
            - request_id: ID запроса
            - queue_position: Позиция в очереди (0 = выполняется сразу, >0 = в очереди)
        """
        request_id = str(uuid.uuid4())

        # Проверяем размер очереди
        if self.queue.full():
            logger.warning(
                f"⚠️ Очередь переполнена ({self.max_queue_size}), отклоняем запрос {request_id}"
            )
            self._stats["total_rejected"] += 1
            return False, request_id, None

        queued = QueuedRequest(
            request_id=request_id,
            priority=priority,
            callback=callback,
            created_at=datetime.now(),
            timeout=timeout,
            metadata=metadata or {},
        )

        try:
            # Добавляем в очередь с приоритетом (меньше = выше приоритет)
            await self.queue.put((priority.value, queued))
            self._stats["total_queued"] += 1
            self._stats["by_priority"][priority] += 1

            queue_position = self.queue.qsize() - 1  # Позиция в очереди (0 = следующий)

            logger.debug(
                f"📥 Запрос {request_id} добавлен в очередь "
                f"(приоритет: {priority.name}, позиция: {queue_position})"
            )

            # Всегда добавляем в очередь, обработка происходит через _process_queue
            # Запускаем обработку очереди, если еще не запущена
            if not self._processing:
                asyncio.create_task(self._process_queue())

            # Проверяем, можем ли выполнить сразу (для информации)
            async with self._lock:
                if self.active_requests < self.max_concurrent:
                    # Есть свободный слот, будет выполнено сразу
                    return True, request_id, 0  # Позиция 0 = будет выполнено сразу

            # Нет свободных слотов, запрос в очереди
            return True, request_id, queue_position

        except Exception as e:
            logger.error(f"❌ Ошибка добавления запроса в очередь: {e}")
            return False, request_id, None

    async def _process_queue(self):
        """Обработать очередь запросов"""
        if self._processing:
            return

        self._processing = True
        logger.debug("🔄 Начало обработки очереди")

        try:
            while True:
                # Проверяем, есть ли свободные слоты
                async with self._lock:
                    if self.active_requests >= self.max_concurrent:
                        # Нет свободных слотов, ждем
                        await asyncio.sleep(0.1)
                        continue

                # Получаем следующий запрос из очереди (приоритетная очередь)
                try:
                    priority_value, request = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=1.0,  # Небольшая задержка для батчинга
                    )
                except asyncio.TimeoutError:
                    # Очередь пуста, проверяем еще раз перед выходом
                    if self.queue.empty() and self.active_requests == 0:
                        break
                    continue

                # Проверяем таймаут
                if request.is_expired():
                    logger.warning(
                        f"⚠️ Запрос {request.request_id} истек по таймауту ({request.timeout}с)"
                    )
                    self._stats["total_expired"] += 1
                    continue

                # Выполняем запрос
                async with self._lock:
                    if self.active_requests >= self.max_concurrent:
                        # Слот занят, возвращаем в очередь
                        await self.queue.put((priority_value, request))
                        await asyncio.sleep(0.1)
                        continue
                    self.active_requests += 1

                logger.debug(
                    f"▶️ Выполняю запрос {request.request_id} "
                    f"(приоритет: {request.priority.name}, "
                    f"активных: {self.active_requests}/{self.max_concurrent})"
                )

                # Запускаем выполнение в отдельной задаче
                asyncio.create_task(self._execute_request(request))

        except Exception as e:
            logger.error(f"❌ Ошибка обработки очереди: {e}", exc_info=True)
        finally:
            self._processing = False
            logger.debug("⏹️ Остановка обработки очереди")

    async def _execute_request(self, request: QueuedRequest):
        """Выполнить запрос"""
        start_time = datetime.now()
        try:
            # Выполняем callback
            result = await request.callback()

            duration = (datetime.now() - start_time).total_seconds()
            logger.debug(
                f"✅ Запрос {request.request_id} выполнен за {duration:.2f}с "
                f"(приоритет: {request.priority.name})"
            )

            self._stats["total_processed"] += 1
            return result

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(
                f"❌ Ошибка выполнения запроса {request.request_id} за {duration:.2f}с: {e}",
                exc_info=True,
            )
            raise
        finally:
            # Освобождаем слот
            async with self._lock:
                self.active_requests = max(0, self.active_requests - 1)

            # Продолжаем обработку очереди
            if not self.queue.empty():
                asyncio.create_task(self._process_queue())

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику очереди"""
        return {
            "active_requests": self.active_requests,
            "max_concurrent": self.max_concurrent,
            "queue_size": self.queue.qsize(),
            "max_queue_size": self.max_queue_size,
            "stats": self._stats.copy(),
            "is_processing": self._processing,
        }

    async def wait_for_slot(self, timeout: float = 60.0) -> bool:
        """
        Ждать освобождения слота (для синхронных вызовов)

        Args:
            timeout: Максимальное время ожидания в секундах

        Returns:
            True если слот освободился, False если таймаут
        """
        start = datetime.now()
        while (datetime.now() - start).total_seconds() < timeout:
            async with self._lock:
                if self.active_requests < self.max_concurrent:
                    return True
            await asyncio.sleep(0.1)
        return False


# Глобальный экземпляр очереди
_request_queue: Optional[MLXRequestQueue] = None


def get_request_queue() -> MLXRequestQueue:
    """Получить глобальный экземпляр очереди"""
    global _request_queue
    if _request_queue is None:
        max_concurrent = int(os.getenv("MLX_MAX_CONCURRENT", "1"))
        max_queue = int(os.getenv("MLX_MAX_QUEUE_SIZE", "50"))
        _request_queue = MLXRequestQueue(max_concurrent=max_concurrent, max_queue_size=max_queue)
        logger.info(
            f"✅ MLX Request Queue инициализирована "
            f"(max_concurrent={max_concurrent}, max_queue={max_queue})"
        )
    return _request_queue
