"""
Redis Streams Infrastructure for Event-Driven Architecture.

Обеспечивает real-time обработку знаний через Redis Streams:
- Consumer Groups для масштабирования
- At-least-once доставка событий
- Автоматическое восстановление при сбоях
"""

from .consumer import ConsumerGroup, EventConsumer
from .events import (
    EventType,
    InsightEvent,
    KnowledgeEvent,
    TaskEvent,
)
from .producer import EventProducer
from .stream_manager import StreamManager

__all__ = [
    # Events
    "KnowledgeEvent",
    "TaskEvent",
    "InsightEvent",
    "EventType",
    # Core
    "StreamManager",
    "EventProducer",
    "EventConsumer",
    "ConsumerGroup",
]
