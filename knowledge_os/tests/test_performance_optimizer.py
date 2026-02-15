"""
Unit tests for Performance Optimizer
"""

import hashlib
import json
import pytest
from knowledge_os.app.performance_optimizer import QueryCache, AsyncTaskQueue, PerformanceMonitor


def _cache_key_hash(query: str, params: tuple) -> str:
    """Хэш ключа кэша (как в QueryCache._make_cache_key)."""
    key_data = f"{query}:{json.dumps(params, sort_keys=True)}"
    return hashlib.md5(key_data.encode()).hexdigest()


@pytest.mark.asyncio
async def test_query_cache():
    """Test query caching"""
    cache = QueryCache()
    
    # Test set and get
    await cache.set("test_query", (), {"result": "test"}, ttl=60)
    result = await cache.get("test_query", ())
    
    assert result is not None
    assert result["result"] == "test"


@pytest.mark.asyncio
async def test_query_cache_invalidation():
    """Test cache invalidation (invalidate по паттерну = хэшу ключа)."""
    cache = QueryCache()
    
    # Set multiple cache entries
    await cache.set("query1", (), {"data": 1})
    await cache.set("query2", (), {"data": 2})
    
    # Invalidate by pattern: ключ в Redis = CACHE_PREFIX + md5("query1:()"), передаём хэш
    pattern = _cache_key_hash("query1", ())
    invalidated = await cache.invalidate(pattern)
    
    # Check that query1 is gone but query2 remains
    result1 = await cache.get("query1", ())
    result2 = await cache.get("query2", ())
    
    assert result1 is None
    assert result2 is not None


@pytest.mark.asyncio
async def test_async_task_queue():
    """Test async task queue"""
    queue = AsyncTaskQueue()
    
    async def test_task(value: int) -> int:
        return value * 2
    
    # Execute single task
    result = await queue.execute_async("test_task", test_task, 5)
    assert result == 10
    
    # Execute batch
    tasks = [
        {"name": "task1", "func": test_task, "args": [1]},
        {"name": "task2", "func": test_task, "args": [2]},
        {"name": "task3", "func": test_task, "args": [3]}
    ]
    
    results = await queue.execute_batch(tasks)
    assert len(results) == 3
    assert results == [2, 4, 6]

