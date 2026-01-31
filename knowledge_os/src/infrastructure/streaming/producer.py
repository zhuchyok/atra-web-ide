"""
Event Producer - публикация событий в Redis Streams.

Обеспечивает:
- Типобезопасную публикацию событий
- Автоматическую сериализацию
- Batch publishing для высокой производительности
- Retry logic для надёжности
"""

import logging
from typing import List, Optional, Dict, Any
import redis.asyncio as redis
import asyncio

from .events import BaseEvent, KnowledgeEvent, TaskEvent, InsightEvent, EventType
from .stream_manager import StreamManager, DEFAULT_STREAMS

logger = logging.getLogger(__name__)


# Маппинг типов событий на streams
EVENT_STREAM_MAP = {
    EventType.KNOWLEDGE_CREATED: "knowledge_stream",
    EventType.KNOWLEDGE_UPDATED: "knowledge_stream",
    EventType.KNOWLEDGE_LINKED: "knowledge_stream",
    EventType.KNOWLEDGE_VERIFIED: "knowledge_stream",
    EventType.TASK_CREATED: "task_stream",
    EventType.TASK_ASSIGNED: "task_stream",
    EventType.TASK_STARTED: "task_stream",
    EventType.TASK_COMPLETED: "task_stream",
    EventType.TASK_FAILED: "task_stream",
    EventType.INSIGHT_DISCOVERED: "insight_stream",
    EventType.INSIGHT_CROSS_DOMAIN: "insight_stream",
    EventType.INSIGHT_HYPOTHESIS: "insight_stream",
    EventType.SYSTEM_HEALTH: "system_stream",
    EventType.SYSTEM_ALERT: "system_stream",
}


class EventProducer:
    """
    Асинхронный producer для публикации событий в Redis Streams.
    
    Использование:
        producer = EventProducer(redis_url)
        await producer.connect()
        
        event = KnowledgeEvent(
            event_type=EventType.KNOWLEDGE_CREATED,
            knowledge_id="123",
            content="New insight..."
        )
        await producer.publish(event)
        
        # Batch publishing
        await producer.publish_batch([event1, event2, event3])
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        max_retries: int = 3,
        retry_delay: float = 0.5
    ):
        self.redis_url = redis_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._redis: Optional[redis.Redis] = None
        self._connected = False
    
    async def connect(self) -> None:
        """Устанавливает соединение с Redis."""
        if self._connected and self._redis:
            return
        
        self._redis = await redis.from_url(
            self.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        try:
            await self._redis.ping()
            self._connected = True
            logger.info("✅ EventProducer connected to Redis")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def _get_stream_for_event(self, event: BaseEvent) -> str:
        """Определяет stream для события."""
        return EVENT_STREAM_MAP.get(event.event_type, "system_stream")
    
    async def publish(
        self,
        event: BaseEvent,
        stream_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Публикует событие в Redis Stream.
        
        Args:
            event: Событие для публикации
            stream_name: Опционально - явное указание stream
            
        Returns:
            Message ID в Redis или None при ошибке
        """
        if not self._connected or not self._redis:
            await self.connect()
        
        target_stream = stream_name or self._get_stream_for_event(event)
        event_data = event.to_dict()
        
        # Получаем max_length для stream
        stream_config = DEFAULT_STREAMS.get(target_stream)
        max_length = stream_config.max_length if stream_config else 10000
        
        for attempt in range(self.max_retries):
            try:
                message_id = await self._redis.xadd(
                    target_stream,
                    event_data,
                    maxlen=max_length
                )
                logger.debug(
                    f"📤 Published {event.event_type.value} to {target_stream}: {message_id}"
                )
                return message_id
            except redis.ConnectionError as e:
                logger.warning(f"Publish attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    await self.connect()  # Reconnect
                else:
                    logger.error(f"Failed to publish event after {self.max_retries} attempts")
                    return None
            except Exception as e:
                logger.error(f"Unexpected error publishing event: {e}")
                return None
        
        return None
    
    async def publish_batch(
        self,
        events: List[BaseEvent],
        stream_name: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Публикует batch событий с использованием pipeline.
        
        Args:
            events: Список событий
            stream_name: Опционально - один stream для всех
            
        Returns:
            Dict с message IDs по streams
        """
        if not self._connected or not self._redis:
            await self.connect()
        
        if not events:
            return {}
        
        results: Dict[str, List[str]] = {}
        
        # Группируем события по streams
        stream_events: Dict[str, List[BaseEvent]] = {}
        for event in events:
            target = stream_name or self._get_stream_for_event(event)
            if target not in stream_events:
                stream_events[target] = []
            stream_events[target].append(event)
        
        # Публикуем через pipeline для каждого stream
        for target_stream, stream_event_list in stream_events.items():
            stream_config = DEFAULT_STREAMS.get(target_stream)
            max_length = stream_config.max_length if stream_config else 10000
            
            try:
                async with self._redis.pipeline() as pipe:
                    for event in stream_event_list:
                        pipe.xadd(target_stream, event.to_dict(), maxlen=max_length)
                    
                    message_ids = await pipe.execute()
                    results[target_stream] = [
                        mid for mid in message_ids if mid is not None
                    ]
                    
                logger.info(
                    f"📤 Batch published {len(results.get(target_stream, []))} "
                    f"events to {target_stream}"
                )
            except Exception as e:
                logger.error(f"Batch publish to {target_stream} failed: {e}")
                results[target_stream] = []
        
        return results
    
    # === Convenience methods для частых типов событий ===
    
    async def publish_knowledge_created(
        self,
        knowledge_id: str,
        content: str,
        domain_id: str,
        domain_name: str,
        confidence_score: float = 0.9,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Публикует событие создания знания."""
        event = KnowledgeEvent(
            event_type=EventType.KNOWLEDGE_CREATED,
            knowledge_id=knowledge_id,
            content=content,
            domain_id=domain_id,
            domain_name=domain_name,
            confidence_score=confidence_score,
            metadata=metadata or {}
        )
        return await self.publish(event)
    
    async def publish_task_created(
        self,
        task_id: str,
        title: str,
        description: str,
        assignee_expert_id: str,
        assignee_name: str,
        creator_expert_id: Optional[str] = None,
        priority: str = "normal",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Публикует событие создания задачи."""
        event = TaskEvent(
            event_type=EventType.TASK_CREATED,
            task_id=task_id,
            title=title,
            description=description,
            assignee_expert_id=assignee_expert_id,
            assignee_name=assignee_name,
            creator_expert_id=creator_expert_id,
            priority=priority,
            metadata=metadata or {}
        )
        return await self.publish(event)
    
    async def publish_task_completed(
        self,
        task_id: str,
        title: str,
        assignee_name: str,
        result: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Публикует событие завершения задачи."""
        event = TaskEvent(
            event_type=EventType.TASK_COMPLETED,
            task_id=task_id,
            title=title,
            assignee_name=assignee_name,
            result=result,
            metadata=metadata or {}
        )
        return await self.publish(event)
    
    async def publish_insight(
        self,
        content: str,
        source_domain: str,
        target_domain: str,
        hypothesis: str,
        confidence: float = 0.9,
        parent_knowledge_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Публикует событие обнаружения инсайта."""
        import json
        event = InsightEvent(
            event_type=EventType.INSIGHT_CROSS_DOMAIN,
            content=content,
            source_domain=source_domain,
            target_domain=target_domain,
            hypothesis=hypothesis,
            confidence=confidence,
            parent_knowledge_ids=json.dumps(parent_knowledge_ids or []),
            metadata=metadata or {}
        )
        return await self.publish(event)
    
    async def close(self) -> None:
        """Закрывает соединение."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self._connected = False
            logger.info("EventProducer connection closed")
