"""
Фаза 4, Неделя 2: Контекстуализация ответов (multi-turn).

ConversationContextManager: хранение истории диалога (session_id → сообщения).
Окно контекста: последние N сообщений, ограничение по токенам (приближённо).
Рекомендации: Backend (единая точка хранения), SRE (TTL, опционально Redis), QA (предсказуемый формат).
"""
import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from app.config import get_settings

logger = logging.getLogger(__name__)

# Приблизительно 4 символа на токен для ограничения контекста
CHARS_PER_TOKEN_APPROX = 4


def _get_redis():
    """Ленивое подключение к Redis (как в rag_context_cache)."""
    try:
        from redis.asyncio import Redis
    except ImportError:
        return None
    settings = get_settings()
    url = getattr(settings, "redis_url", None) or os.getenv("REDIS_URL")
    if not url:
        return None
    try:
        import redis.asyncio as aioredis
        return aioredis.from_url(url, decode_responses=True)
    except Exception as e:
        logger.debug("ConversationContext Redis init skipped: %s", e)
        return None


class ConversationContextManager:
    """
    Управление контекстом диалога для multi-turn чата.
    Хранилище: in-memory с TTL; опционально Redis по конфигу.
    """

    def __init__(
        self,
        ttl_sec: int = 3600,
        max_messages_per_session: int = 50,
        max_context_chars: int = 8000,
        use_redis: bool = False,
    ):
        self.ttl_sec = ttl_sec
        self.max_messages_per_session = max_messages_per_session
        self.max_context_chars = max_context_chars
        self.use_redis = use_redis
        self._memory: Dict[str, List[Dict[str, Any]]] = {}
        self._memory_ts: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def append(self, session_id: str, role: str, content: str) -> None:
        """Добавить сообщение в историю сессии. role: 'user' | 'assistant'."""
        if not session_id or not content:
            return
        item = {"role": role, "content": content[:50000], "ts": time.time()}
        async with self._lock:
            self._memory_ts[session_id] = time.time()
            if session_id not in self._memory:
                self._memory[session_id] = []
            self._memory[session_id].append(item)
            if len(self._memory[session_id]) > self.max_messages_per_session:
                self._memory[session_id] = self._memory[session_id][-self.max_messages_per_session:]
        if self.use_redis:
            await self._redis_append(session_id, item)

    async def get_recent(
        self,
        session_id: str,
        last_n: int = 10,
        max_chars: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Последние сообщения сессии (окно контекста).
        Сначала берём из Redis при use_redis, иначе из memory; обрезаем по last_n и max_chars.
        """
        if not session_id:
            return []
        max_chars = max_chars or self.max_context_chars
        messages: List[Dict[str, Any]] = []
        if self.use_redis:
            messages = await self._redis_get_recent(session_id, last_n)
        async with self._lock:
            if session_id in self._memory_ts:
                if time.time() - self._memory_ts[session_id] > self.ttl_sec:
                    self._memory.pop(session_id, None)
                    self._memory_ts.pop(session_id, None)
                    return []
            if not messages and session_id in self._memory:
                messages = list(self._memory[session_id][-last_n:])
        # Ограничение по длине
        total = 0
        out: List[Dict[str, Any]] = []
        for m in reversed(messages):
            c = (m.get("content") or "")[:50000]
            if total + len(c) > max_chars:
                break
            out.insert(0, m)
            total += len(c)
        return out

    def build_context_prefix(self, messages: List[Dict[str, Any]]) -> str:
        """
        Форматирование истории для префикса к промпту.
        Рекомендация Technical Writer: единообразные формулировки «Пользователь» / «Ассистент».
        """
        if not messages:
            return ""
        lines = []
        for m in messages:
            role = m.get("role", "user")
            content = (m.get("content") or "").strip()
            if not content:
                continue
            label = "Пользователь" if role == "user" else "Ассистент"
            lines.append(f"{label}: {content}")
        if not lines:
            return ""
        return "Предыдущий диалог:\n" + "\n".join(lines) + "\n\n"

    def to_victoria_chat_history(self, messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Конвертирует [{"role", "content"}] в формат Victoria [{"user", "assistant"}]."""
        if not messages:
            return []
        out: List[Dict[str, str]] = []
        current: Dict[str, str] = {}
        for m in messages:
            role = m.get("role", "user")
            content = (m.get("content") or "").strip()
            if role == "user":
                if current.get("assistant"):
                    out.append(current)
                current = {"user": content, "assistant": ""}
            else:
                current["assistant"] = content
        if current.get("user") or current.get("assistant"):
            out.append(current)
        return out

    async def clear(self, session_id: str) -> None:
        """Очистить историю сессии."""
        if not session_id:
            return
        async with self._lock:
            self._memory.pop(session_id, None)
            self._memory_ts.pop(session_id, None)
        if self.use_redis:
            await self._redis_clear(session_id)

    async def _redis_append(self, session_id: str, item: Dict[str, Any]) -> None:
        r = _get_redis()
        if not r:
            return
        try:
            key = f"conv_ctx:{session_id}"
            await r.rpush(key, json.dumps(item, ensure_ascii=False))
            await r.expire(key, self.ttl_sec)
            await r.ltrim(key, -self.max_messages_per_session, -1)
        except Exception as e:
            logger.debug("ConversationContext Redis append failed: %s", e)

    async def _redis_get_recent(self, session_id: str, last_n: int) -> List[Dict[str, Any]]:
        r = _get_redis()
        if not r:
            return []
        try:
            key = f"conv_ctx:{session_id}"
            raw = await r.lrange(key, -last_n, -1)
            return [json.loads(x) for x in raw if x]
        except Exception as e:
            logger.debug("ConversationContext Redis get failed: %s", e)
            return []

    async def _redis_clear(self, session_id: str) -> None:
        r = _get_redis()
        if not r:
            return
        try:
            await r.delete(f"conv_ctx:{session_id}")
        except Exception as e:
            logger.debug("ConversationContext Redis clear failed: %s", e)


_conversation_context_manager: Optional[ConversationContextManager] = None


def get_conversation_context_manager() -> ConversationContextManager:
    """Singleton ConversationContextManager (как get_rag_context_cache)."""
    global _conversation_context_manager
    if _conversation_context_manager is None:
        settings = get_settings()
        ttl = int(getattr(settings, "conversation_context_ttl_sec", 3600))
        max_messages = int(getattr(settings, "conversation_context_max_messages", 50))
        max_chars = int(getattr(settings, "conversation_context_max_chars", 8000))
        use_redis = getattr(settings, "conversation_context_use_redis", False)
        _conversation_context_manager = ConversationContextManager(
            ttl_sec=ttl,
            max_messages_per_session=max_messages,
            max_context_chars=max_chars,
            use_redis=use_redis,
        )
    return _conversation_context_manager
