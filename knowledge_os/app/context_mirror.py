import redis
import json
import logging
import os

logger = logging.getLogger(__name__)

class ContextMirror:
    """
    Зеркалирование контекста сессии в Redis для быстрого переключения между MLX и Ollama.
    """
    def __init__(self, redis_url: str = None):
        url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis = redis.from_url(url, decode_responses=True)
        logger.info("ContextMirror initialized with Redis at %s", url)
    
    async def save_context(self, session_id: str, history: list, ttl: int = 3600):
        """Сохранить историю сообщений сессии в Redis."""
        try:
            key = f"context:{session_id}"
            self.redis.set(key, json.dumps(history), ex=ttl)
            logger.debug("Saved context for session %s (history len: %d)", session_id, len(history))
        except Exception as e:
            logger.error("Failed to save context to Redis: %s", e)
        
    async def get_context(self, session_id: str) -> list:
        """Получить историю сообщений сессии из Redis."""
        try:
            key = f"context:{session_id}"
            data = self.redis.get(key)
            if data:
                history = json.loads(data)
                logger.debug("Retrieved context for session %s (history len: %d)", session_id, len(history))
                return history
        except Exception as e:
            logger.error("Failed to get context from Redis: %s", e)
        return []

    def clear_context(self, session_id: str):
        """Удалить контекст сессии."""
        try:
            self.redis.delete(f"context:{session_id}")
        except Exception as e:
            logger.error("Failed to delete context from Redis: %s", e)
