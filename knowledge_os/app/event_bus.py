"""
Event-Driven Architecture - Асинхронная обработка событий
Основано на Microsoft AutoGen v0.4: event-driven и request/response паттерны
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from collections import defaultdict
import uuid

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Типы событий"""
    # Существующие события
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    AGENT_MESSAGE = "agent_message"
    KNOWLEDGE_UPDATED = "knowledge_updated"
    MODEL_RESPONSE = "model_response"
    SYSTEM_EVENT = "system_event"
    
    # Новые события для инициативы (Event-Driven Architecture)
    FILE_CREATED = "file_created"
    FILE_MODIFIED = "file_modified"
    FILE_DELETED = "file_deleted"
    SERVICE_DOWN = "service_down"
    SERVICE_UP = "service_up"
    SERVICE_HEALTH_CHECK = "service_health_check"
    DEADLINE_APPROACHING = "deadline_approaching"
    DEADLINE_PASSED = "deadline_passed"
    ERROR_DETECTED = "error_detected"
    PERFORMANCE_DEGRADED = "performance_degraded"
    
    # События для саморасширения (Skill Registry)
    SKILL_NEEDED = "skill_needed"
    SKILL_ADDED = "skill_added"
    SKILL_UPDATED = "skill_updated"
    SKILL_REMOVED = "skill_removed"
    SKILL_LOADED = "skill_loaded"


@dataclass
class Event:
    """Событие в системе"""
    event_id: str
    event_type: EventType
    payload: Dict[str, Any]
    source: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = None


class EventBus:
    """
    Event Bus - центральная шина событий для асинхронной коммуникации
    
    Паттерны:
    - Publish/Subscribe
    - Request/Response
    - Event-driven workflow
    """
    
    def __init__(self):
        self.subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.event_history: List[Event] = []
        self.max_history: int = 1000
        self.running: bool = False
        self._processor_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Запустить обработчик событий"""
        if self.running:
            return
        
        self.running = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("🚀 Event Bus запущен")
    
    async def stop(self):
        """Остановить обработчик событий"""
        self.running = False
        if self._processor_task:
            await self._processor_task
        logger.info("🛑 Event Bus остановлен")
    
    async def publish(self, event: Event):
        """
        Опубликовать событие
        
        Args:
            event: Событие для публикации
        """
        await self.event_queue.put(event)
        logger.debug(f"📢 Событие опубликовано: {event.event_type.value} от {event.source}")
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """
        Подписаться на события
        
        Args:
            event_type: Тип события
            handler: Обработчик (async функция)
        """
        self.subscribers[event_type].append(handler)
        logger.debug(f"✅ Подписка на {event_type.value}: {handler.__name__}")
    
    def unsubscribe(self, event_type: EventType, handler: Callable):
        """Отписаться от событий"""
        if handler in self.subscribers[event_type]:
            self.subscribers[event_type].remove(handler)
            logger.debug(f"❌ Отписка от {event_type.value}: {handler.__name__}")
    
    async def request_response(
        self,
        event_type: EventType,
        payload: Dict[str, Any],
        source: str,
        timeout: float = 30.0
    ) -> Optional[Dict]:
        """
        Request/Response паттерн
        
        Args:
            event_type: Тип события
            payload: Данные запроса
            source: Источник
            timeout: Таймаут ожидания ответа
        
        Returns:
            Ответ или None
        """
        correlation_id = str(uuid.uuid4())
        
        # Создаем событие запроса
        request_event = Event(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            payload={**payload, "_correlation_id": correlation_id, "_is_request": True},
            source=source,
            correlation_id=correlation_id
        )
        
        # Создаем Future для ответа
        response_future = asyncio.Future()
        response_events = {}
        response_events[correlation_id] = response_future
        
        # Публикуем запрос
        await self.publish(request_event)
        
        # Ждем ответ
        try:
            response = await asyncio.wait_for(response_future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ Таймаут ожидания ответа на {event_type.value}")
            return None
        finally:
            response_events.pop(correlation_id, None)
    
    async def _process_events(self):
        """Обработчик событий (работает в фоне)"""
        while self.running:
            try:
                # Получаем событие из очереди
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                
                # Сохраняем в историю
                self.event_history.append(event)
                if len(self.event_history) > self.max_history:
                    self.event_history.pop(0)
                
                # Находим подписчиков
                handlers = self.subscribers.get(event.event_type, [])
                
                # Вызываем обработчики параллельно
                if handlers:
                    tasks = [handler(event) for handler in handlers]
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Обрабатываем request/response
                if event.payload.get("_is_request"):
                    await self._handle_request(event)
                elif event.correlation_id:
                    await self._handle_response(event)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"❌ Ошибка обработки события: {e}")
    
    async def _handle_request(self, event: Event):
        """Обработать запрос (для request/response)"""
        # В реальной системе здесь была бы маршрутизация к обработчику
        logger.debug(f"📥 Обработка запроса: {event.event_id}")
    
    async def _handle_response(self, event: Event):
        """Обработать ответ (для request/response)"""
        # В реальной системе здесь был бы поиск соответствующего Future
        logger.debug(f"📤 Обработка ответа: {event.event_id}")
    
    def get_event_history(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        """Получить историю событий"""
        events = self.event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return events[-limit:]
    
    def get_stats(self) -> Dict:
        """Получить статистику Event Bus"""
        stats = {
            "total_events": len(self.event_history),
            "subscribers": {et.value: len(handlers) for et, handlers in self.subscribers.items()},
            "queue_size": self.event_queue.qsize(),
            "running": self.running
        }
        return stats


# Глобальный экземпляр Event Bus
_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Получить глобальный Event Bus"""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus


async def main():
    """Пример использования"""
    bus = get_event_bus()
    await bus.start()
    
    # Подписываемся на события
    async def handle_task_created(event: Event):
        print(f"📥 Получено событие: {event.event_type.value} от {event.source}")
        print(f"   Payload: {event.payload}")
    
    bus.subscribe(EventType.TASK_CREATED, handle_task_created)
    
    # Публикуем событие
    event = Event(
        event_id=str(uuid.uuid4()),
        event_type=EventType.TASK_CREATED,
        payload={"task": "Пример задачи"},
        source="test_agent"
    )
    
    await bus.publish(event)
    
    # Ждем обработки
    await asyncio.sleep(0.1)
    
    # Статистика
    print(f"\nСтатистика: {bus.get_stats()}")
    
    await bus.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
