"""
Enhanced Caching для Victoria Enhanced
Кэширование результатов Extended Thinking, Tree of Thoughts и других методов
"""

import hashlib
import json
import time
import asyncio
import os
from typing import Dict, Optional, Any, List
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

# Попытка использовать существующий PromptCache
try:
    from app.prompt_cache import PromptCache
    PROMPT_CACHE_AVAILABLE = True
except ImportError:
    PROMPT_CACHE_AVAILABLE = False
    logger.debug("ℹ️ PromptCache не доступен (опциональный компонент)")

class EnhancedCache:
    """Кэш для результатов Enhanced методов"""
    
    def __init__(self, ttl_seconds: int = 3600, max_size: int = 1000):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_times: Dict[str, float] = {}
        
        # Используем PromptCache если доступен
        self.prompt_cache = None
        if PROMPT_CACHE_AVAILABLE:
            try:
                self.prompt_cache = PromptCache()
            except Exception as e:
                logger.debug(f"ℹ️ Не удалось инициализировать PromptCache: {e} (опциональный компонент)")
    
    def _get_cache_key(self, method: str, goal: str, context: Optional[Dict] = None) -> str:
        """Генерация ключа кэша"""
        cache_data = {
            "method": method,
            "goal": goal,
            "context": context or {}
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()
    
    async def get(self, method: str, goal: str, context: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """Получить из кэша"""
        cache_key = self._get_cache_key(method, goal, context)
        
        # Проверяем in-memory кэш
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if time.time() - entry["timestamp"] < self.ttl_seconds:
                self._access_times[cache_key] = time.time()
                logger.debug(f"✅ Cache hit: {method}")
                return entry["result"]
            else:
                # TTL истек
                del self._cache[cache_key]
                del self._access_times[cache_key]
        
        # Проверяем PromptCache (для совместимости)
        if self.prompt_cache:
            try:
                prompt_key = f"{method}:{goal[:100]}"
                cached = await self.prompt_cache.get_cached_response(prompt_key, "enhanced")
                if cached:
                    logger.debug(f"✅ PromptCache hit: {method}")
                    return json.loads(cached) if isinstance(cached, str) else cached
            except Exception as e:
                logger.debug(f"PromptCache check failed: {e}")
        
        logger.debug(f"❌ Cache miss: {method}")
        return None
    
    async def set(self, method: str, goal: str, result: Dict[str, Any], context: Optional[Dict] = None):
        """Сохранить в кэш"""
        cache_key = self._get_cache_key(method, goal, context)
        
        # Сохраняем в in-memory кэш
        self._cache[cache_key] = {
            "result": result,
            "timestamp": time.time(),
            "method": method
        }
        self._access_times[cache_key] = time.time()
        
        # Очистка старых записей если превышен лимит
        if len(self._cache) > self.max_size:
            self._evict_oldest()
        
        # Сохраняем в PromptCache (для персистентности)
        if self.prompt_cache:
            try:
                prompt_key = f"{method}:{goal[:100]}"
                await self.prompt_cache.cache_response(
                    prompt_key,
                    "enhanced",
                    json.dumps(result),
                    ttl_seconds=self.ttl_seconds
                )
            except Exception as e:
                logger.debug(f"PromptCache save failed: {e}")
    
    def _evict_oldest(self):
        """Удалить самые старые записи"""
        if not self._access_times:
            return
        
        # Сортируем по времени доступа
        sorted_keys = sorted(self._access_times.items(), key=lambda x: x[1])
        
        # Удаляем 10% самых старых
        evict_count = max(1, len(sorted_keys) // 10)
        for key, _ in sorted_keys[:evict_count]:
            self._cache.pop(key, None)
            self._access_times.pop(key, None)
    
    def clear(self):
        """Очистить кэш"""
        self._cache.clear()
        self._access_times.clear()
        logger.info("🗑️ Enhanced cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику кэша"""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "oldest_entry": min(self._access_times.values()) if self._access_times else None,
            "newest_entry": max(self._access_times.values()) if self._access_times else None
        }

# Глобальный экземпляр
_enhanced_cache: Optional[EnhancedCache] = None

def get_enhanced_cache() -> EnhancedCache:
    """Получить глобальный экземпляр кэша"""
    global _enhanced_cache
    if _enhanced_cache is None:
        ttl = int(os.getenv("ENHANCED_CACHE_TTL", "3600"))
        max_size = int(os.getenv("ENHANCED_CACHE_MAX_SIZE", "1000"))
        _enhanced_cache = EnhancedCache(ttl_seconds=ttl, max_size=max_size)
    return _enhanced_cache
