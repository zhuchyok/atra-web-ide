"""
Event Consumer - потребление событий из Redis Streams.

Обеспечивает:
- Consumer Groups для масштабирования
- At-least-once доставку
- Автоматический recovery зависших сообщений
- Graceful shutdown
"""

import logging
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, List, Optional, Dict, Any, Awaitable
import redis.asyncio as redis
import signal
import uuid

from .events import BaseEvent, deserialize_event, EventType

logger = logging.getLogger(__name__)


@dataclass
class ConsumerConfig:
    """Конфигурация consumer."""
    
    stream_name: str
    group_name: str
    consumer_name: str = ""  # Auto-generated if empty
    batch_size: int = 10
    block_ms: int = 5000  # Время ожидания новых сообщений
    claim_idle_ms: int = 60000  # Время для claim зависших сообщений
    max_retries: int = 3
    ack_after_process: bool = True  # ACK после успешной обработки


class ConsumerGroup:
    """
    Представляет consumer group с метриками.
    """
    
    def __init__(self, name: str, stream_name: str):
        self.name = name
        self.stream_name = stream_name
        self.consumers: List[str] = []
        self.processed_count = 0
        self.failed_count = 0


EventHandler = Callable[[BaseEvent, Dict[str, Any]], Awaitable[bool]]


class EventConsumer:
    """
    Асинхронный consumer для чтения событий из Redis Streams.
    
    Использование:
        consumer = EventConsumer(
            redis_url="redis://localhost:6379",
            config=ConsumerConfig(
                stream_name="knowledge_stream",
                group_name="knowledge_processors",
            )
        )
        
        @consumer.on_event(EventType.KNOWLEDGE_CREATED)
        async def handle_knowledge(event: KnowledgeEvent, raw_data: dict):
            print(f"New knowledge: {event.content}")
            return True  # ACK message
        
        await consumer.start()
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        config: Optional[ConsumerConfig] = None
    ):
        self.redis_url = redis_url
        self.config = config or ConsumerConfig(
            stream_name="knowledge_stream",
            group_name="knowledge_processors"
        )
        
        # Generate unique consumer name if not provided
        if not self.config.consumer_name:
            self.config.consumer_name = f"consumer-{uuid.uuid4().hex[:8]}"
        
        self._redis: Optional[redis.Redis] = None
        self._running = False
        self._handlers: Dict[EventType, List[EventHandler]] = {}
        self._default_handler: Optional[EventHandler] = None
        
        # Metrics
        self.processed_count = 0
        self.failed_count = 0
        self.last_message_id: Optional[str] = None
    
    async def connect(self) -> None:
        """Устанавливает соединение с Redis."""
        self._redis = await redis.from_url(
            self.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=10
        )
        
        try:
            await self._redis.ping()
            logger.info(f"✅ Consumer '{self.config.consumer_name}' connected to Redis")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect: {e}")
            raise
        
        # Ensure consumer group exists
        try:
            await self._redis.xgroup_create(
                self.config.stream_name,
                self.config.group_name,
                id="$",
                mkstream=True
            )
            logger.info(f"Created consumer group '{self.config.group_name}'")
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
    
    def on_event(self, event_type: EventType) -> Callable:
        """
        Decorator для регистрации обработчика события.
        
        @consumer.on_event(EventType.KNOWLEDGE_CREATED)
        async def handle(event, raw_data):
            return True
        """
        def decorator(func: EventHandler) -> EventHandler:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(func)
            logger.debug(f"Registered handler for {event_type.value}")
            return func
        return decorator
    
    def set_default_handler(self, handler: EventHandler) -> None:
        """Устанавливает обработчик по умолчанию для всех событий."""
        self._default_handler = handler
    
    def add_handler(self, event_type: EventType, handler: EventHandler) -> None:
        """Программная регистрация обработчика."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    async def _process_message(
        self,
        message_id: str,
        message_data: Dict[str, str]
    ) -> bool:
        """Обрабатывает одно сообщение."""
        try:
            event = deserialize_event(message_data)
            
            # Находим обработчики
            handlers = self._handlers.get(event.event_type, [])
            if not handlers and self._default_handler:
                handlers = [self._default_handler]
            
            if not handlers:
                logger.warning(
                    f"No handler for event type {event.event_type.value}, ACKing anyway"
                )
                return True
            
            # Вызываем все обработчики
            success = True
            for handler in handlers:
                try:
                    result = await handler(event, message_data)
                    if not result:
                        success = False
                except Exception as e:
                    logger.error(f"Handler error for {event.event_type.value}: {e}")
                    success = False
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to process message {message_id}: {e}")
            return False
    
    async def _claim_pending_messages(self) -> List[tuple]:
        """Забирает зависшие сообщения от неактивных consumers."""
        if not self._redis:
            return []
        
        try:
            result = await self._redis.xautoclaim(
                self.config.stream_name,
                self.config.group_name,
                self.config.consumer_name,
                min_idle_time=self.config.claim_idle_ms,
                count=self.config.batch_size
            )
            messages = result[1] if len(result) > 1 else []
            if messages:
                logger.info(f"🔄 Claimed {len(messages)} pending messages")
            return messages
        except Exception as e:
            logger.warning(f"Failed to claim pending messages: {e}")
            return []
    
    async def _read_new_messages(self) -> List[tuple]:
        """Читает новые сообщения из stream."""
        if not self._redis:
            return []
        
        try:
            # > означает читать только новые сообщения для этого consumer
            result = await self._redis.xreadgroup(
                groupname=self.config.group_name,
                consumername=self.config.consumer_name,
                streams={self.config.stream_name: ">"},
                count=self.config.batch_size,
                block=self.config.block_ms
            )
            
            if result:
                # result = [(stream_name, [(msg_id, fields), ...])]
                return result[0][1]
            return []
            
        except Exception as e:
            logger.error(f"Failed to read messages: {e}")
            return []
    
    async def _ack_message(self, message_id: str) -> bool:
        """Подтверждает обработку сообщения."""
        if not self._redis:
            return False
        
        try:
            await self._redis.xack(
                self.config.stream_name,
                self.config.group_name,
                message_id
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to ACK message {message_id}: {e}")
            return False
    
    async def start(self) -> None:
        """
        Запускает consumer loop.
        Блокирующий метод - выполняется до остановки.
        """
        await self.connect()
        self._running = True
        
        logger.info(
            f"🚀 Consumer '{self.config.consumer_name}' started "
            f"(stream: {self.config.stream_name}, group: {self.config.group_name})"
        )
        
        while self._running:
            try:
                # 1. Сначала пробуем забрать зависшие сообщения
                pending_messages = await self._claim_pending_messages()
                
                # 2. Затем читаем новые
                new_messages = await self._read_new_messages()
                
                all_messages = pending_messages + new_messages
                
                for message_id, message_data in all_messages:
                    self.last_message_id = message_id
                    
                    success = await self._process_message(message_id, message_data)
                    
                    if success:
                        self.processed_count += 1
                        if self.config.ack_after_process:
                            await self._ack_message(message_id)
                    else:
                        self.failed_count += 1
                        # Не ACKаем - сообщение останется в pending
                        logger.warning(
                            f"Message {message_id} processing failed, "
                            "will be redelivered"
                        )
                
            except asyncio.CancelledError:
                logger.info("Consumer cancelled, shutting down...")
                break
            except Exception as e:
                logger.error(f"Consumer loop error: {e}")
                await asyncio.sleep(1)  # Backoff before retry
        
        await self.stop()
    
    async def stop(self) -> None:
        """Останавливает consumer."""
        self._running = False
        
        if self._redis:
            await self._redis.close()
            self._redis = None
        
        logger.info(
            f"Consumer '{self.config.consumer_name}' stopped. "
            f"Processed: {self.processed_count}, Failed: {self.failed_count}"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику consumer."""
        return {
            "consumer_name": self.config.consumer_name,
            "stream": self.config.stream_name,
            "group": self.config.group_name,
            "running": self._running,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "last_message_id": self.last_message_id,
        }


class MultiStreamConsumer:
    """
    Consumer для нескольких streams одновременно.
    Полезно для обработки связанных событий из разных streams.
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        consumer_name: Optional[str] = None
    ):
        self.redis_url = redis_url
        self.consumer_name = consumer_name or f"multi-consumer-{uuid.uuid4().hex[:8]}"
        self._consumers: Dict[str, EventConsumer] = {}
        self._tasks: List[asyncio.Task] = []
        self._running = False
    
    def add_stream(
        self,
        stream_name: str,
        group_name: str,
        handlers: Optional[Dict[EventType, EventHandler]] = None
    ) -> EventConsumer:
        """Добавляет stream для обработки."""
        config = ConsumerConfig(
            stream_name=stream_name,
            group_name=group_name,
            consumer_name=f"{self.consumer_name}-{stream_name}"
        )
        
        consumer = EventConsumer(self.redis_url, config)
        
        if handlers:
            for event_type, handler in handlers.items():
                consumer.add_handler(event_type, handler)
        
        self._consumers[stream_name] = consumer
        return consumer
    
    async def start(self) -> None:
        """Запускает все consumers параллельно."""
        self._running = True
        
        for stream_name, consumer in self._consumers.items():
            task = asyncio.create_task(
                consumer.start(),
                name=f"consumer-{stream_name}"
            )
            self._tasks.append(task)
        
        logger.info(f"🚀 MultiStreamConsumer started with {len(self._tasks)} streams")
        
        # Ждём завершения всех tasks
        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            await self.stop()
    
    async def stop(self) -> None:
        """Останавливает все consumers."""
        self._running = False
        
        for task in self._tasks:
            task.cancel()
        
        for consumer in self._consumers.values():
            await consumer.stop()
        
        self._tasks.clear()
        logger.info("MultiStreamConsumer stopped")
