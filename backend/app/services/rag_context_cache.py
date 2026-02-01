"""
RAG Context Cache — кэш результатов векторного поиска (Ollama + MLX контекст).
Снижает latency при повторных запросах: embedding + БД не вызываются.
"""
import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.config import get_settings

logger = logging.getLogger(__name__)

_redis_client = None
_cache_monitor: Optional["CacheMonitor"] = None


class CacheMonitor:
    """Счётчик hits/misses для мониторинга эффективности кэша."""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.hits_local = 0
        self.hits_redis = 0
        self.start_time = datetime.now()

    def record_hit(self, source: str = "local"):
        self.hits += 1
        if source == "redis":
            self.hits_redis += 1
        else:
            self.hits_local += 1

    def record_miss(self):
        self.misses += 1

    def get_stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0.0
        return {
            "hit_rate_pct": round(hit_rate, 1),
            "hits": self.hits,
            "misses": self.misses,
            "hits_local": self.hits_local,
            "hits_redis": self.hits_redis,
            "total": total,
            "uptime_sec": (datetime.now() - self.start_time).total_seconds(),
        }


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as aioredis
        settings = get_settings()
        url = getattr(settings, "redis_url", None) or os.getenv("REDIS_URL")
        if url:
            _redis_client = aioredis.from_url(url, decode_responses=True)
            return _redis_client
    except Exception as e:
        logger.debug("Redis for RAG cache: %s", e)
    return None


def _generate_key(
    goal: str,
    user_id: Optional[str] = None,
    collection: str = "default",
    embedding_model: Optional[str] = None,
    limit: int = 3,
    threshold: float = 0.65,
) -> str:
    """Уникальный ключ с учётом всех параметров запроса."""
    settings = get_settings()
    components = {
        "goal": (goal or "").strip().lower(),
        "user_id": user_id or "global",
        "collection": collection,
        "embedding_model": embedding_model or getattr(settings, "ollama_embed_model", "nomic-embed-text"),
        "limit": limit,
        "threshold": round(threshold, 2),
    }
    key_str = json.dumps(components, sort_keys=True)
    h = hashlib.sha256(key_str.encode()).hexdigest()[:24]
    return f"rag_ctx:{h}"


_rag_context_cache: Optional["RAGContextCache"] = None


def get_cache_monitor() -> "CacheMonitor":
    """Глобальный монитор кэша для API."""
    global _cache_monitor
    if _cache_monitor is None:
        _cache_monitor = CacheMonitor()
    return _cache_monitor


def get_rag_context_cache(ttl: int = 300, use_redis: bool = True) -> "RAGContextCache":
    """Singleton RAGContextCache для Auto-Optimizer и RAGLightService."""
    global _rag_context_cache
    if _rag_context_cache is None:
        _rag_context_cache = RAGContextCache(ttl=ttl, use_redis=use_redis)
    return _rag_context_cache


class RAGContextCache:
    """Кэш контекста RAG (результаты векторного поиска)."""

    def __init__(
        self,
        ttl: int = 300,
        use_redis: bool = True,
        local_maxsize: int = 200,
    ):
        self.ttl = ttl
        self.use_redis = use_redis
        self._local: Dict[str, Tuple[List[Tuple[str, float]], float]] = {}
        self._local_max = local_maxsize
        self.monitor = get_cache_monitor()
        self._min_ttl = 60
        self._max_ttl = 600

    def get_current_ttl(self) -> int:
        """Текущий TTL в секундах (для Auto-Optimizer)."""
        return self.ttl

    def set_ttl(self, ttl: int) -> None:
        """Динамическое изменение TTL (для Auto-Optimizer)."""
        self.ttl = max(self._min_ttl, min(ttl, self._max_ttl))

    async def get_context(
        self,
        goal: str,
        user_id: Optional[str] = None,
        limit: int = 3,
        threshold: float = 0.65,
    ) -> Optional[List[Tuple[str, float]]]:
        """Получить кэшированный контекст [(content, score), ...]."""
        key = _generate_key(goal, user_id, limit=limit, threshold=threshold)

        if key in self._local:
            chunks, _ = self._local[key]
            self.monitor.record_hit("local")
            logger.info("✅ RAG cache hit (local): %s...", (goal or "")[:40])
            return chunks

        if self.use_redis:
            r = _get_redis()
            if r:
                try:
                    raw = await r.get(key)
                    if raw:
                        data = json.loads(raw)
                        chunks = [tuple(c) for c in data.get("chunks", [])]
                        self.monitor.record_hit("redis")
                        logger.info("✅ RAG cache hit (redis): %s...", (goal or "")[:40])
                        return chunks
                except Exception as e:
                    logger.debug("RAG cache redis get: %s", e)

        self.monitor.record_miss()
        logger.debug("🔄 RAG cache miss: %s...", (goal or "")[:40])
        return None

    async def save_context(
        self,
        goal: str,
        chunks: List[Tuple[str, float]],
        user_id: Optional[str] = None,
        limit: int = 3,
        threshold: float = 0.65,
    ) -> None:
        """Сохранить контекст в кэш."""
        if not chunks:
            return
        key = _generate_key(goal, user_id, limit=limit, threshold=threshold)
        data = {"chunks": list(chunks)}

        while len(self._local) >= self._local_max and self._local:
            self._local.pop(next(iter(self._local)))
        self._local[key] = (chunks, 0.0)

        if self.use_redis:
            r = _get_redis()
            if r:
                try:
                    await r.setex(key, self.ttl, json.dumps(data, ensure_ascii=False))
                except Exception as e:
                    logger.debug("RAG cache redis set: %s", e)

    async def clear_all(self) -> int:
        """
        Очистка кэша (Self-healing: при падении качества RAG — инвалидация кэша).
        Рекомендации Backend (Игорь): единая точка инвалидации для пайплайна качества.
        Возвращает число очищенных ключей (local + redis).
        """
        count = len(self._local)
        self._local.clear()
        if self.use_redis:
            r = _get_redis()
            if r:
                try:
                    keys = await r.keys("rag_ctx:*")
                    if keys:
                        await r.delete(*keys)
                        count += len(keys)
                except Exception as e:
                    logger.debug("RAG cache redis clear: %s", e)
        logger.info("RAG context cache cleared: %s entries", count)
        return count
