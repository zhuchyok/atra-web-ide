"""
Redis Stream Manager - централизованное управление streams и consumer groups.

Отвечает за:
- Создание и конфигурацию streams
- Управление consumer groups
- Мониторинг здоровья streams
- Очистку старых сообщений
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import redis.asyncio as redis

logger = logging.getLogger(__name__)


@dataclass
class StreamConfig:
    """Конфигурация отдельного stream."""
    
    name: str
    max_length: int = 10000  # Максимальное кол-во сообщений (MAXLEN ~)
    consumer_groups: List[str] = field(default_factory=list)
    retention_hours: int = 24


# Предопределённые streams системы
DEFAULT_STREAMS: Dict[str, StreamConfig] = {
    "knowledge_stream": StreamConfig(
        name="knowledge_stream",
        max_length=50000,
        consumer_groups=["knowledge_processors", "analytics", "notifiers"],
        retention_hours=72
    ),
    "task_stream": StreamConfig(
        name="task_stream",
        max_length=10000,
        consumer_groups=["task_workers", "monitors"],
        retention_hours=48
    ),
    "insight_stream": StreamConfig(
        name="insight_stream",
        max_length=20000,
        consumer_groups=["insight_processors", "cross_domain_linkers"],
        retention_hours=168  # 1 неделя для инсайтов
    ),
    "system_stream": StreamConfig(
        name="system_stream",
        max_length=5000,
        consumer_groups=["monitors", "alerters"],
        retention_hours=24
    ),
}


class StreamManager:
    """
    Управляет Redis Streams для Knowledge OS.
    
    Использование:
        manager = StreamManager(redis_url)
        await manager.initialize()
        
        # Получение информации
        info = await manager.get_stream_info("knowledge_stream")
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        streams: Optional[Dict[str, StreamConfig]] = None
    ):
        self.redis_url = redis_url
        self.streams = streams or DEFAULT_STREAMS
        self._redis: Optional[redis.Redis] = None
        self._initialized = False
    
    async def _get_redis(self) -> redis.Redis:
        """Lazy initialization Redis клиента."""
        if self._redis is None:
            self._redis = await redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
        return self._redis
    
    async def initialize(self) -> None:
        """
        Инициализирует все streams и consumer groups.
        Безопасно вызывать многократно (idempotent).
        """
        if self._initialized:
            return
        
        rd = await self._get_redis()
        
        for stream_name, config in self.streams.items():
            # Создаём stream (добавляя и удаляя dummy сообщение)
            try:
                await rd.xadd(
                    stream_name,
                    {"init": "stream_manager_init"},
                    maxlen=config.max_length
                )
                logger.info(f"✅ Stream '{stream_name}' initialized")
            except Exception as e:
                logger.warning(f"Stream '{stream_name}' init warning: {e}")
            
            # Создаём consumer groups
            for group_name in config.consumer_groups:
                try:
                    # MKSTREAM создаст stream если не существует
                    # $ = читать только новые сообщения
                    await rd.xgroup_create(
                        stream_name,
                        group_name,
                        id="$",
                        mkstream=True
                    )
                    logger.info(f"✅ Consumer group '{group_name}' created for '{stream_name}'")
                except redis.ResponseError as e:
                    if "BUSYGROUP" in str(e):
                        # Группа уже существует - это нормально
                        logger.debug(f"Consumer group '{group_name}' already exists")
                    else:
                        logger.error(f"Failed to create consumer group '{group_name}': {e}")
        
        self._initialized = True
        logger.info("🚀 StreamManager initialized successfully")
    
    async def get_stream_info(self, stream_name: str) -> Dict[str, Any]:
        """Получает информацию о stream."""
        rd = await self._get_redis()
        
        try:
            info = await rd.xinfo_stream(stream_name)
            groups = await rd.xinfo_groups(stream_name)
            
            return {
                "name": stream_name,
                "length": info.get("length", 0),
                "first_entry": info.get("first-entry"),
                "last_entry": info.get("last-entry"),
                "consumer_groups": [
                    {
                        "name": g.get("name"),
                        "consumers": g.get("consumers", 0),
                        "pending": g.get("pending", 0),
                        "last_delivered_id": g.get("last-delivered-id"),
                    }
                    for g in groups
                ]
            }
        except redis.ResponseError as e:
            logger.warning(f"Could not get info for stream '{stream_name}': {e}")
            return {"name": stream_name, "error": str(e)}
    
    async def get_pending_messages(
        self,
        stream_name: str,
        group_name: str,
        count: int = 100
    ) -> List[Dict[str, Any]]:
        """Получает список pending сообщений для group."""
        rd = await self._get_redis()
        
        try:
            pending = await rd.xpending_range(
                stream_name,
                group_name,
                min="-",
                max="+",
                count=count
            )
            return [
                {
                    "message_id": p.get("message_id"),
                    "consumer": p.get("consumer"),
                    "time_since_delivered": p.get("time_since_delivered"),
                    "times_delivered": p.get("times_delivered"),
                }
                for p in pending
            ]
        except redis.ResponseError as e:
            logger.warning(f"Could not get pending for '{stream_name}/{group_name}': {e}")
            return []
    
    async def claim_stale_messages(
        self,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        min_idle_time_ms: int = 60000,  # 1 минута
        count: int = 10
    ) -> List[tuple]:
        """
        Забирает 'зависшие' сообщения от неактивных consumers.
        Используется для recovery при падении worker'а.
        """
        rd = await self._get_redis()
        
        try:
            # XAUTOCLAIM автоматически забирает idle сообщения
            result = await rd.xautoclaim(
                stream_name,
                group_name,
                consumer_name,
                min_idle_time=min_idle_time_ms,
                count=count
            )
            # result = (next_start_id, [(msg_id, fields), ...])
            messages = result[1] if len(result) > 1 else []
            if messages:
                logger.info(f"🔄 Claimed {len(messages)} stale messages for '{consumer_name}'")
            return messages
        except redis.ResponseError as e:
            logger.warning(f"Could not claim messages: {e}")
            return []
    
    async def trim_stream(self, stream_name: str, max_length: Optional[int] = None) -> int:
        """Обрезает stream до max_length сообщений."""
        rd = await self._get_redis()
        config = self.streams.get(stream_name)
        max_len = max_length or (config.max_length if config else 10000)
        
        try:
            # XTRIM с ~ для approximate trimming (более эффективно)
            deleted = await rd.xtrim(stream_name, maxlen=max_len, approximate=True)
            if deleted > 0:
                logger.info(f"🧹 Trimmed {deleted} messages from '{stream_name}'")
            return deleted
        except redis.ResponseError as e:
            logger.warning(f"Could not trim stream '{stream_name}': {e}")
            return 0
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья всех streams."""
        rd = await self._get_redis()
        
        try:
            await rd.ping()
            
            streams_health = {}
            for stream_name in self.streams:
                info = await self.get_stream_info(stream_name)
                streams_health[stream_name] = {
                    "healthy": "error" not in info,
                    "length": info.get("length", 0),
                    "groups": len(info.get("consumer_groups", [])),
                }
            
            return {
                "status": "healthy",
                "redis_connected": True,
                "streams": streams_health,
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "redis_connected": False,
                "error": str(e),
            }
    
    async def close(self) -> None:
        """Закрывает соединение с Redis."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self._initialized = False
            logger.info("StreamManager connection closed")
