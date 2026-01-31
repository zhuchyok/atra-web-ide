#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚌 Event Bus для Event-Driven Architecture

Реализует publish-subscribe паттерн для:
- Декомпозиции системы
- Слабой связанности компонентов
- Масштабируемости

Автор: Игорь (Backend Developer) - Learning Session #5
Основано на: "Enterprise Integration Patterns"
"""

import asyncio
import logging
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now
from enum import Enum
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Типы событий"""
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_ACCEPTED = "signal_accepted"
    SIGNAL_REJECTED = "signal_rejected"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    ML_PREDICTION = "ml_prediction"
    RISK_ALERT = "risk_alert"
    SYSTEM_ERROR = "system_error"
    MARKET_DATA_UPDATE = "market_data_update"


@dataclass
class Event:
    """Событие в системе"""
    event_type: EventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=get_utc_now)
    source: str = "unknown"
    event_id: Optional[str] = None


class EventBus:
    """
    Event Bus для event-driven архитектуры
    
    Использование:
        bus = EventBus()
        
        async def handler(event: Event):
            print(f"Received: {event.event_type}")
        
        bus.subscribe(EventType.SIGNAL_GENERATED, handler)
        await bus.publish(EventType.SIGNAL_GENERATED, {"symbol": "BTCUSDT"})
    """
    
    def __init__(self):
        self.subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._lock = threading.Lock()
        self._stats = {
            'events_published': 0,
            'events_handled': 0,
            'events_failed': 0
        }
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """
        Подписка на событие
        
        Args:
            event_type: Тип события
            handler: Функция-обработчик (async или sync)
        """
        with self._lock:
            if handler not in self.subscribers[event_type]:
                self.subscribers[event_type].append(handler)
                logger.debug(f"✅ Подписка на {event_type.value}: {handler.__name__}")
            else:
                logger.warning(f"⚠️ Handler уже подписан: {handler.__name__}")
    
    def unsubscribe(self, event_type: EventType, handler: Callable):
        """Отписка от события"""
        with self._lock:
            if handler in self.subscribers[event_type]:
                self.subscribers[event_type].remove(handler)
                logger.debug(f"❌ Отписка от {event_type.value}: {handler.__name__}")
    
    async def publish(self, event_type: EventType, data: Dict[str, Any], source: str = "unknown") -> int:
        """
        Публикация события
        
        Args:
            event_type: Тип события
            data: Данные события
            source: Источник события
        
        Returns:
            Количество обработанных handlers
        """
        event = Event(
            event_type=event_type,
            data=data,
            source=source,
            timestamp=get_utc_now()
        )
        
        handlers = self.subscribers.get(event_type, [])
        
        if not handlers:
            logger.debug(f"⚠️ Нет подписчиков на {event_type.value}")
            return 0
        
        self._stats['events_published'] += 1
        
        # Вызываем все handlers
        tasks = []
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    task = asyncio.create_task(handler(event))
                    tasks.append(task)
                else:
                    # Sync handler
                    handler(event)
                    self._stats['events_handled'] += 1
            except Exception as e:
                logger.error(f"❌ Ошибка в handler {handler.__name__}: {e}")
                self._stats['events_failed'] += 1
        
        # Ждём async handlers
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    self._stats['events_failed'] += 1
                else:
                    self._stats['events_handled'] += 1
        
        logger.debug(f"📢 Событие {event_type.value} опубликовано, обработано handlers: {len(handlers)}")
        
        return len(handlers)
    
    def publish_sync(self, event_type: EventType, data: Dict[str, Any], source: str = "unknown") -> int:
        """
        Синхронная публикация события
        
        Args:
            event_type: Тип события
            data: Данные события
            source: Источник события
        
        Returns:
            Количество обработанных handlers
        """
        event = Event(
            event_type=event_type,
            data=data,
            source=source,
            timestamp=get_utc_now()
        )
        
        handlers = self.subscribers.get(event_type, [])
        
        if not handlers:
            return 0
        
        self._stats['events_published'] += 1
        
        # Вызываем все handlers синхронно
        for handler in handlers:
            try:
                handler(event)
                self._stats['events_handled'] += 1
            except Exception as e:
                logger.error(f"❌ Ошибка в handler {handler.__name__}: {e}")
                self._stats['events_failed'] += 1
        
        return len(handlers)
    
    def get_stats(self) -> Dict[str, int]:
        """Возвращает статистику"""
        return self._stats.copy()
    
    def get_subscribers_count(self) -> Dict[str, int]:
        """Возвращает количество подписчиков по типам событий"""
        return {et.value: len(handlers) for et, handlers in self.subscribers.items()}


# Глобальный event bus
_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Получить глобальный event bus"""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus


if __name__ == "__main__":
    # Пример использования
    logging.basicConfig(level=logging.INFO)
    
    async def signal_handler(event: Event):
        print(f"📊 Signal handler: {event.data}")
    
    async def risk_handler(event: Event):
        print(f"⚠️ Risk alert: {event.data}")
    
    async def main():
        bus = get_event_bus()
        
        # Подписки
        bus.subscribe(EventType.SIGNAL_GENERATED, signal_handler)
        bus.subscribe(EventType.RISK_ALERT, risk_handler)
        
        # Публикация
        await bus.publish(EventType.SIGNAL_GENERATED, {"symbol": "BTCUSDT", "price": 50000})
        await bus.publish(EventType.RISK_ALERT, {"level": "high", "message": "High risk detected"})
        
        print(f"\n📊 Stats: {bus.get_stats()}")
        print(f"📊 Subscribers: {bus.get_subscribers_count()}")
    
    asyncio.run(main())

