"""
Event types для Knowledge OS streaming architecture.

Все события наследуют BaseEvent и могут быть сериализованы в Redis Streams.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import json
import uuid


class EventType(str, Enum):
    """Типы событий в системе."""
    
    # Knowledge events
    KNOWLEDGE_CREATED = "knowledge.created"
    KNOWLEDGE_UPDATED = "knowledge.updated"
    KNOWLEDGE_LINKED = "knowledge.linked"
    KNOWLEDGE_VERIFIED = "knowledge.verified"
    
    # Task events
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    
    # Insight events
    INSIGHT_DISCOVERED = "insight.discovered"
    INSIGHT_CROSS_DOMAIN = "insight.cross_domain"
    INSIGHT_HYPOTHESIS = "insight.hypothesis"
    
    # System events
    SYSTEM_HEALTH = "system.health"
    SYSTEM_ALERT = "system.alert"


@dataclass
class BaseEvent:
    """Базовый класс для всех событий."""
    
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = field(default=EventType.SYSTEM_HEALTH)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = "knowledge_os"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, str]:
        """Сериализация в формат для Redis Streams (все значения - строки)."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["metadata"] = json.dumps(data["metadata"])
        return {k: str(v) if not isinstance(v, str) else v for k, v in data.items()}
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "BaseEvent":
        """Десериализация из Redis Streams."""
        data = dict(data)
        if "event_type" in data:
            data["event_type"] = EventType(data["event_type"])
        if "metadata" in data:
            try:
                data["metadata"] = json.loads(data["metadata"])
            except json.JSONDecodeError:
                data["metadata"] = {}
        return cls(**data)


@dataclass
class KnowledgeEvent(BaseEvent):
    """Событие, связанное со знаниями."""
    
    knowledge_id: Optional[str] = None
    domain_id: Optional[str] = None
    domain_name: str = ""
    content: str = ""
    confidence_score: float = 0.0
    parent_ids: str = "[]"  # JSON list of parent knowledge IDs
    
    def to_dict(self) -> Dict[str, str]:
        data = super().to_dict()
        data["confidence_score"] = str(self.confidence_score)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "KnowledgeEvent":
        data = dict(data)
        if "event_type" in data:
            data["event_type"] = EventType(data["event_type"])
        if "metadata" in data:
            try:
                data["metadata"] = json.loads(data["metadata"])
            except json.JSONDecodeError:
                data["metadata"] = {}
        if "confidence_score" in data:
            data["confidence_score"] = float(data["confidence_score"])
        return cls(**data)


@dataclass
class TaskEvent(BaseEvent):
    """Событие, связанное с задачами."""
    
    task_id: Optional[str] = None
    title: str = ""
    description: str = ""
    assignee_expert_id: Optional[str] = None
    assignee_name: str = ""
    creator_expert_id: Optional[str] = None
    priority: str = "normal"  # low, normal, high, critical
    result: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "TaskEvent":
        data = dict(data)
        if "event_type" in data:
            data["event_type"] = EventType(data["event_type"])
        if "metadata" in data:
            try:
                data["metadata"] = json.loads(data["metadata"])
            except json.JSONDecodeError:
                data["metadata"] = {}
        return cls(**data)


@dataclass
class InsightEvent(BaseEvent):
    """Событие открытия инсайта."""
    
    insight_id: Optional[str] = None
    content: str = ""
    source_domain: str = ""
    target_domain: str = ""
    hypothesis: str = ""
    confidence: float = 0.0
    parent_knowledge_ids: str = "[]"  # JSON list
    
    def to_dict(self) -> Dict[str, str]:
        data = super().to_dict()
        data["confidence"] = str(self.confidence)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "InsightEvent":
        data = dict(data)
        if "event_type" in data:
            data["event_type"] = EventType(data["event_type"])
        if "metadata" in data:
            try:
                data["metadata"] = json.loads(data["metadata"])
            except json.JSONDecodeError:
                data["metadata"] = {}
        if "confidence" in data:
            data["confidence"] = float(data["confidence"])
        return cls(**data)


# Маппинг типов событий на классы
EVENT_CLASS_MAP = {
    EventType.KNOWLEDGE_CREATED: KnowledgeEvent,
    EventType.KNOWLEDGE_UPDATED: KnowledgeEvent,
    EventType.KNOWLEDGE_LINKED: KnowledgeEvent,
    EventType.KNOWLEDGE_VERIFIED: KnowledgeEvent,
    EventType.TASK_CREATED: TaskEvent,
    EventType.TASK_ASSIGNED: TaskEvent,
    EventType.TASK_STARTED: TaskEvent,
    EventType.TASK_COMPLETED: TaskEvent,
    EventType.TASK_FAILED: TaskEvent,
    EventType.INSIGHT_DISCOVERED: InsightEvent,
    EventType.INSIGHT_CROSS_DOMAIN: InsightEvent,
    EventType.INSIGHT_HYPOTHESIS: InsightEvent,
    EventType.SYSTEM_HEALTH: BaseEvent,
    EventType.SYSTEM_ALERT: BaseEvent,
}


def deserialize_event(data: Dict[str, str]) -> BaseEvent:
    """Универсальная десериализация события по его типу."""
    event_type_str = data.get("event_type", "system.health")
    try:
        event_type = EventType(event_type_str)
    except ValueError:
        event_type = EventType.SYSTEM_HEALTH
    
    event_class = EVENT_CLASS_MAP.get(event_type, BaseEvent)
    return event_class.from_dict(data)
