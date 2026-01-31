"""
Кэширование для Singularity 9.0
In-memory cache с TTL и LRU eviction
"""
import time
import logging
from typing import Any, Optional, Dict
from collections import OrderedDict
import hashlib
import json

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CacheEntry:
    """Запись в кэше"""
    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
    
    def is_expired(self) -> bool:
        """Проверить, истек ли TTL"""
        return time.time() - self.created_at > self.ttl


class LRUCache:
    """LRU Cache с TTL для Singularity 9.0"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
    
    def _generate_key(self, *args, **kwargs) -> str:
        """Генерировать ключ кэша"""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша"""
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        
        # Проверяем TTL
        if entry.is_expired():
            del self.cache[key]
            return None
        
        # Перемещаем в конец (LRU)
        self.cache.move_to_end(key)
        
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Установить значение в кэш"""
        ttl = ttl or self.default_ttl
        
        # Если ключ уже существует, обновляем
        if key in self.cache:
            self.cache.move_to_end(key)
        
        # Добавляем новую запись
        self.cache[key] = CacheEntry(value, ttl)
        
        # Если превышен размер, удаляем самый старый
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)
    
    def delete(self, key: str) -> None:
        """Удалить ключ из кэша"""
        if key in self.cache:
            del self.cache[key]
    
    def clear(self) -> None:
        """Очистить весь кэш"""
        self.cache.clear()
    
    def cleanup_expired(self) -> int:
        """Очистить истекшие записи"""
        expired_keys = [
            key for key, entry in self.cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)


# Глобальный экземпляр кэша
_cache: Optional[LRUCache] = None


def get_cache() -> LRUCache:
    """Получить глобальный экземпляр кэша"""
    global _cache
    if _cache is None:
        _cache = LRUCache(
            max_size=1000,
            default_ttl=settings.cache_ttl
        )
    return _cache


def cache_key(*args, **kwargs) -> str:
    """Генерировать ключ кэша"""
    cache = get_cache()
    return cache._generate_key(*args, **kwargs)
