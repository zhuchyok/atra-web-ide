"""
Performance Optimizer: Оптимизация производительности запросов

Функционал:
- Кэширование сложных вычислений
- Асинхронная обработка тяжелых задач
- Мониторинг производительности
- Автоматическая оптимизация
"""

import asyncio
import os
import json
import asyncpg
import redis.asyncio as redis
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from functools import wraps
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

# Настройки кэширования
CACHE_TTL = 3600  # 1 час
CACHE_PREFIX = "knowledge_os:cache:"


class QueryCache:
    """Класс для кэширования результатов запросов"""
    
    def __init__(self, redis_url: str = REDIS_URL):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
    
    async def get_redis(self) -> redis.Redis:
        """Получение Redis клиента"""
        if self.redis_client is None:
            self.redis_client = await redis.from_url(self.redis_url, decode_responses=True)
        return self.redis_client
    
    def _make_cache_key(self, query: str, params: tuple = ()) -> str:
        """Создание ключа кэша из запроса и параметров"""
        key_data = f"{query}:{json.dumps(params, sort_keys=True)}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{CACHE_PREFIX}{key_hash}"
    
    async def get(self, query: str, params: tuple = ()) -> Optional[Any]:
        """Получение результата из кэша"""
        try:
            rd = await self.get_redis()
            cache_key = self._make_cache_key(query, params)
            cached = await rd.get(cache_key)
            
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    async def set(self, query: str, params: tuple, result: Any, ttl: int = CACHE_TTL) -> bool:
        """Сохранение результата в кэш"""
        try:
            rd = await self.get_redis()
            cache_key = self._make_cache_key(query, params)
            await rd.setex(cache_key, ttl, json.dumps(result, default=str))
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    async def invalidate(self, pattern: str) -> int:
        """Инвалидация кэша по паттерну"""
        try:
            rd = await self.get_redis()
            keys = await rd.keys(f"{CACHE_PREFIX}*{pattern}*")
            if keys:
                return await rd.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache invalidate error: {e}")
            return 0
    
    async def clear_all(self) -> bool:
        """Очистка всего кэша"""
        try:
            rd = await self.get_redis()
            keys = await rd.keys(f"{CACHE_PREFIX}*")
            if keys:
                await rd.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False


def cached_query(ttl: int = CACHE_TTL):
    """Декоратор для кэширования результатов запросов"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = QueryCache()
            
            # Создаем ключ кэша из функции и аргументов
            cache_key = f"{func.__name__}:{json.dumps(args, sort_keys=True)}:{json.dumps(kwargs, sort_keys=True)}"
            
            # Пытаемся получить из кэша
            cached = await cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit: {func.__name__}")
                return cached
            
            # Выполняем запрос
            result = await func(*args, **kwargs)
            
            # Сохраняем в кэш
            await cache.set(cache_key, (), result, ttl)
            logger.debug(f"Cache miss: {func.__name__}")
            
            return result
        return wrapper
    return decorator


class AsyncTaskQueue:
    """Очередь для асинхронной обработки тяжелых задач"""
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.max_workers = 5
        self.semaphore = asyncio.Semaphore(self.max_workers)
    
    async def execute_async(
        self,
        task_name: str,
        task_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Выполнение задачи асинхронно с ограничением параллелизма"""
        async with self.semaphore:
            try:
                logger.info(f"Starting async task: {task_name}")
                start_time = datetime.now()
                
                result = await task_func(*args, **kwargs)
                
                duration = (datetime.now() - start_time).total_seconds()
                logger.info(f"Completed async task: {task_name} (took {duration:.2f}s)")
                
                return result
            except Exception as e:
                logger.error(f"Async task error: {task_name}: {e}")
                raise
    
    async def execute_batch(
        self,
        tasks: List[Dict[str, Any]]
    ) -> List[Any]:
        """Выполнение батча задач параллельно"""
        async def execute_task(task):
            return await self.execute_async(
                task['name'],
                task['func'],
                *task.get('args', []),
                **task.get('kwargs', {})
            )
        
        results = await asyncio.gather(*[execute_task(task) for task in tasks])
        return results


class PerformanceMonitor:
    """Мониторинг производительности запросов"""
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
    
    async def get_slow_queries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Получение списка медленных запросов"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                rows = await conn.fetch("""
                    SELECT * FROM analyze_slow_queries()
                """)
                return [dict(row) for row in rows[:limit]]
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error getting slow queries: {e}")
            return []
    
    async def get_query_stats(self) -> Dict[str, Any]:
        """Получение статистики запросов"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                stats = await conn.fetchrow("""
                    SELECT 
                        count(*) as total_queries,
                        sum(calls) as total_calls,
                        avg(mean_exec_time) as avg_exec_time,
                        max(mean_exec_time) as max_exec_time
                    FROM pg_stat_statements
                """)
                
                return {
                    "total_queries": stats['total_queries'] or 0,
                    "total_calls": stats['total_calls'] or 0,
                    "avg_exec_time_ms": round(float(stats['avg_exec_time'] or 0), 2),
                    "max_exec_time_ms": round(float(stats['max_exec_time'] or 0), 2)
                }
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error getting query stats: {e}")
            return {}
    
    async def refresh_cache(self) -> bool:
        """Обновление материализованных представлений (кэша)"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                await conn.execute("SELECT refresh_performance_cache()")
                logger.info("✅ Performance cache refreshed")
                return True
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error refreshing cache: {e}")
            return False


async def run_performance_optimization():
    """Запуск оптимизации производительности"""
    logger.info("🚀 Starting performance optimization...")
    
    monitor = PerformanceMonitor()
    cache = QueryCache()
    
    # 1. Обновляем кэш
    await monitor.refresh_cache()
    
    # 2. Анализируем медленные запросы
    slow_queries = await monitor.get_slow_queries()
    if slow_queries:
        logger.warning(f"Found {len(slow_queries)} slow queries")
        for query in slow_queries[:5]:
            logger.warning(f"  - {query.get('query_text', '')[:100]}... (avg: {query.get('mean_time', 0):.2f}ms)")
    
    # 3. Получаем статистику
    stats = await monitor.get_query_stats()
    logger.info(f"Query stats: {stats}")
    
    logger.info("✅ Performance optimization completed")


if __name__ == "__main__":
    asyncio.run(run_performance_optimization())

