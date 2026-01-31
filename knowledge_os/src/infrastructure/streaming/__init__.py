"""
Redis Streams Infrastructure for Event-Driven Architecture.

Обеспечивает real-time обработку знаний через Redis Streams:
- Consumer Groups для масштабирования
- At-least-once доставка событий
- Автоматическое восстановление при сбоях
"""

from .events import (
    KnowledgeEvent,
    TaskEvent,
    InsightEvent,
    EventType,
)
from .stream_manager import StreamManager
from .producer import EventProducer
from .consumer import EventConsumer, ConsumerGroup

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
