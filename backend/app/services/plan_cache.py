"""
Кэш планов (Фаза 3): двухуровневый кэш (память + опционально Redis).
Ускоряет повторные запросы планов по одному и тому же goal + project_context.
"""
import hashlib
import logging
import pickle
from typing import Any, Dict, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

try:
    from cachetools import TTLCache
except ImportError:
    TTLCache = None  # type: ignore

_redis_client = None


def _get_redis_client():
    """Опциональный Redis-клиент (async). Требует redis>=5.0."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as aioredis
        settings = get_settings()
        url = getattr(settings, "redis_url", None) or getattr(settings, "REDIS_URL", None)
        if url:
            _redis_client = aioredis.from_url(url, decode_responses=False)
            return _redis_client
    except ImportError:
        logger.debug("Redis package not installed, plan cache will use memory only")
    except Exception as e:
        logger.debug("Redis not available for plan cache: %s", e)
    return None


class PlanCacheService:
    """Двухуровневый кэш для планов: память (TTL) + опционально Redis."""

    def __init__(
        self,
        redis_client: Any = None,
        use_redis: bool = False,
        maxsize: int = 100,
        ttl: int = 3600,
    ):
        self._maxsize = maxsize
        self._ttl = ttl
        self.use_redis = use_redis and (redis_client is not None or _get_redis_client() is not None)
        self.redis = redis_client or (_get_redis_client() if self.use_redis else None)
        if maxsize == 0 or TTLCache is None:
            self.local_cache: Dict[str, Any] = {}
        else:
            self.local_cache = TTLCache(maxsize=maxsize, ttl=ttl)

    def _generate_key(self, goal: str, project_context: Optional[str] = None) -> str:
        normalized = " ".join((goal or "").strip().lower().split())
        if project_context:
            normalized += f":{project_context.strip().lower()}"
        h = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        return f"plan:{h}"

    async def get(
        self, goal: str, project_context: Optional[str] = None
    ) -> Optional[Dict]:
        key = self._generate_key(goal, project_context)

        if key in self.local_cache:
            try:
                from app.metrics.prometheus_metrics import PLAN_CACHE_HITS, record_cache_hit
                PLAN_CACHE_HITS.inc()
                record_cache_hit("plan_cache")
            except Exception:
                pass
            logger.debug("Plan cache hit (local): %s", key)
            return self.local_cache[key]

        if self.use_redis and self.redis:
            try:
                cached = await self.redis.get(key)
                if cached:
                    try:
                        from app.metrics.prometheus_metrics import PLAN_CACHE_HITS, record_cache_hit
                        PLAN_CACHE_HITS.inc()
                        record_cache_hit("plan_cache")
                    except Exception:
                        pass
                    plan = pickle.loads(cached)
                    self.local_cache[key] = plan
                    logger.debug("Plan cache hit (redis): %s", key)
                    return plan
            except Exception as e:
                logger.warning("Redis plan cache get error: %s", e)
        return None

    async def set(
        self,
        goal: str,
        plan: Dict,
        project_context: Optional[str] = None,
        ttl: int = 3600,
    ) -> None:
        if self._maxsize == 0:
            return
        key = self._generate_key(goal, project_context)
        self.local_cache[key] = plan

        if self.use_redis and self.redis:
            try:
                serialized = pickle.dumps(plan)
                await self.redis.setex(key, ttl, serialized)
                logger.debug("Plan saved to cache: %s", key)
            except Exception as e:
                logger.error("Failed to save plan to Redis: %s", e)

    async def clear(
        self,
        goal: Optional[str] = None,
        project_context: Optional[str] = None,
    ) -> None:
        if goal is not None:
            key = self._generate_key(goal, project_context)
            if key in self.local_cache:
                del self.local_cache[key]
            if self.use_redis and self.redis:
                try:
                    await self.redis.delete(key)
                except Exception as e:
                    logger.warning("Redis plan cache delete error: %s", e)
        else:
            self.local_cache.clear()
            if self.use_redis and self.redis:
                try:
                    keys = await self.redis.keys("plan:*")
                    if keys:
                        await self.redis.delete(*keys)
                except Exception as e:
                    logger.warning("Redis plan cache clear error: %s", e)

    async def stats(self) -> Dict:
        size = len(self.local_cache) if hasattr(self.local_cache, "__len__") else 0
        try:
            from app.metrics.prometheus_metrics import update_cache_size
            update_cache_size("plan_cache", size)
        except Exception:
            pass
        out = {"local_cache_size": size}
        if self.use_redis and self.redis:
            try:
                keys = await self.redis.keys("plan:*")
                out["redis_cache_size"] = len(keys)
            except Exception as e:
                out["redis_error"] = str(e)
        return out


_plan_cache_instance: Optional[PlanCacheService] = None


def get_plan_cache_service() -> PlanCacheService:
    """Синглтон кэша планов (создаётся по настройкам)."""
    global _plan_cache_instance
    if _plan_cache_instance is None:
        settings = get_settings()
        enabled = getattr(settings, "plan_cache_enabled", True)
        if not enabled:
            # Отключён: пустой кэш, get всегда None, set ничего не делает по сути
            _plan_cache_instance = PlanCacheService(
                use_redis=False, maxsize=0, ttl=0
            )
        else:
            use_redis = getattr(settings, "plan_cache_redis_enabled", False)
            redis_client = _get_redis_client() if use_redis else None
            _plan_cache_instance = PlanCacheService(
                redis_client=redis_client,
                use_redis=bool(redis_client),
                maxsize=getattr(settings, "plan_cache_maxsize", 100),
                ttl=getattr(settings, "plan_cache_ttl", 3600),
            )
    return _plan_cache_instance
