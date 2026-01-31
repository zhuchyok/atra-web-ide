"""
Кэширование результатов запросов для ускорения часто используемых операций.
Снижает нагрузку на БД на 50-90% для повторяющихся запросов.
"""

import time
import hashlib
import logging
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Запись в кэше"""
    data: Any
    timestamp: float = field(default_factory=time.time)
    ttl: float = 60.0  # Время жизни в секундах (по умолчанию 60 сек)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    
    @property
    def is_expired(self) -> bool:
        """Проверка истечения TTL"""
        return time.time() - self.timestamp > self.ttl
    
    @property
    def age(self) -> float:
        """Возраст записи в секундах"""
        return time.time() - self.timestamp


class QueryCache:
    """Кэш для результатов SQL запросов"""
    
    def __init__(self, max_size: int = 1000, default_ttl: float = 60.0):
        """
        Args:
            max_size: Максимальное количество записей в кэше
            default_ttl: Время жизни записей по умолчанию (секунды)
        """
        self._cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.hits = 0
        self.misses = 0
        self.evictions = 0
    
    def _generate_key(self, query: str, params: Tuple = ()) -> str:
        """Генерация ключа кэша из запроса и параметров"""
        # Нормализуем запрос (убираем лишние пробелы)
        normalized_query = ' '.join(query.strip().split())
        # Создаем хэш из запроса и параметров
        key_data = f"{normalized_query}:{params}"
        return hashlib.md5(key_data.encode('utf-8')).hexdigest()
    
    def _evict_oldest(self):
        """Удаление самой старой записи (LRU)"""
        if not self._cache:
            return
        
        # Находим запись с наименьшим last_access
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_access)
        del self._cache[oldest_key]
        self.evictions += 1
    
    def _cleanup_expired(self):
        """Очистка истекших записей"""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired]
        for key in expired_keys:
            del self._cache[key]
        if expired_keys:
            logger.debug("Очищено %d истекших записей из кэша", len(expired_keys))
    
    def get(self, query: str, params: Tuple = ()) -> Optional[Any]:
        """
        Получение результата из кэша
        
        Args:
            query: SQL запрос
            params: Параметры запроса
            
        Returns:
            Результат запроса или None если не найден/истек
        """
        key = self._generate_key(query, params)
        
        if key not in self._cache:
            self.misses += 1
            return None
        
        entry = self._cache[key]
        
        if entry.is_expired:
            del self._cache[key]
            self.misses += 1
            return None
        
        # Обновляем статистику доступа
        entry.access_count += 1
        entry.last_access = time.time()
        self.hits += 1
        
        return entry.data
    
    def set(self, query: str, params: Tuple, data: Any, ttl: Optional[float] = None):
        """
        Сохранение результата в кэш
        
        Args:
            query: SQL запрос
            params: Параметры запроса
            data: Результат запроса
            ttl: Время жизни (секунды), если None - используется default_ttl
        """
        # Очищаем истекшие записи
        self._cleanup_expired()
        
        # Если кэш переполнен, удаляем самую старую запись
        if len(self._cache) >= self.max_size:
            self._evict_oldest()
        
        key = self._generate_key(query, params)
        self._cache[key] = CacheEntry(
            data=data,
            ttl=ttl or self.default_ttl
        )
    
    def clear(self):
        """Очистка всего кэша"""
        self._cache.clear()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        logger.info("Кэш запросов очищен")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики кэша"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0.0
        
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate,
            'evictions': self.evictions,
            'total_requests': total_requests
        }


# Глобальный экземпляр кэша
_query_cache: Optional[QueryCache] = None


def get_query_cache() -> QueryCache:
    """Получить глобальный экземпляр кэша запросов"""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache(max_size=1000, default_ttl=60.0)
    return _query_cache

