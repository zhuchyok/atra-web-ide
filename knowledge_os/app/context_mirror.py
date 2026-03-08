import json
import logging
import os
from typing import Any, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class ContextMirror:
    """
    ContextMirror handles session history mirroring between different LLM nodes (MLX and Ollama)
    using Redis as a central store. This ensures that failover from MLX to Ollama
    preserves the conversation history.
    """

    def __init__(self, redis_url: Optional[str] = None, ttl: int = 3600):
        """
        Initialize ContextMirror.

        Args:
            redis_url: Redis connection URL. Defaults to REDIS_URL environment variable
                       or redis://localhost:6379/0.
            ttl: Time-to-live for session context in seconds. Defaults to 1 hour (3600s).
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.ttl = ttl
        self._redis_client: Optional[redis.Redis] = None

    async def _get_client(self) -> Optional[redis.Redis]:
        """Lazy initialization of Redis client."""
        if self._redis_client is not None:
            return self._redis_client

        try:
            self._redis_client = redis.from_url(self.redis_url, decode_responses=True)
            return self._redis_client
        except Exception as e:
            logger.error(f"❌ Error connecting to Redis: {e}")
            return None

    async def save_context(self, session_id: str, history: list[Any]) -> bool:
        """
        Save session history to Redis using atomic list operations.

        Args:
            session_id: Unique identifier for the session.
            history: List of message objects (dicts) representing the history.

        Returns:
            bool: True if saved successfully, False otherwise.
        """
        if not session_id or history is None:
            return False

        client = await self._get_client()
        if not client:
            return False

        try:
            key = f"context:list:{session_id}"
            # Используем пайплайн для атомарности
            pipe = await client.pipeline(transaction=True)
            # Очищаем старый список (или можно просто дописывать, но для зеркала лучше перезапись)
            await pipe.delete(key)
            for msg in history:
                await pipe.rpush(key, json.dumps(msg))
            # Ограничиваем длину списка (например, последние 50 сообщений)
            await pipe.ltrim(key, -50, -1)
            await pipe.expire(key, self.ttl)
            await pipe.execute()

            # Также сохраняем как строку для обратной совместимости (опционально)
            await client.setex(f"context:{session_id}", self.ttl, json.dumps(history))

            return True
        except Exception as e:
            logger.error(f"❌ Error saving atomic context for session {session_id}: {e}")
            return False

    async def get_context(self, session_id: str) -> Optional[list[Any]]:
        """
        Retrieve session history from Redis using list operations.

        Args:
            session_id: Unique identifier for the session.

        Returns:
            Optional[List[Any]]: The history list if found, None otherwise.
        """
        if not session_id:
            return None

        client = await self._get_client()
        if not client:
            return None

        try:
            key = f"context:list:{session_id}"
            # Пробуем сначала список
            data_list = await client.lrange(key, 0, -1)
            if data_list:
                return [json.loads(m) for m in data_list]

            # Fallback на старый формат строки
            key_old = f"context:{session_id}"
            data = await client.get(key_old)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"❌ Error retrieving atomic context for session {session_id}: {e}")
            return None
