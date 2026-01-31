"""
Тесты кэша планов (Фаза 3).
Запуск: cd backend && python -m pytest app/tests/test_plan_cache.py -v
"""
import asyncio

from app.services.plan_cache import PlanCacheService


def _cache():
    return PlanCacheService(use_redis=False, maxsize=100, ttl=3600)


def test_plan_cache_set_get():
    async def _run():
        cache = _cache()
        goal = "настроить CI/CD"
        plan = {"status": "success", "result": "1. Установить runner\n2. Добавить pipeline", "response": "1. Установить runner\n2. Добавить pipeline"}
        await cache.set(goal, plan)
        cached = await cache.get(goal)
        assert cached is not None
        assert cached.get("result") == plan["result"]
    asyncio.run(_run())


def test_plan_cache_key_includes_project_context():
    async def _run():
        cache = _cache()
        goal = "развернуть приложение"
        plan = {"status": "success", "result": "Plan A"}
        await cache.set(goal, plan, project_context="atra")
        assert await cache.get(goal, "atra") is not None
        assert await cache.get(goal, "atra-web-ide") is None
        assert await cache.get(goal, None) is None
    asyncio.run(_run())


def test_plan_cache_clear():
    async def _run():
        cache = _cache()
        goal = "тест очистки"
        await cache.set(goal, {"result": "x"})
        assert await cache.get(goal) is not None
        await cache.clear(goal=goal)
        assert await cache.get(goal) is None
    asyncio.run(_run())


def test_plan_cache_stats():
    async def _run():
        cache = _cache()
        await cache.set("goal1", {"result": "a"})
        stats = await cache.stats()
        assert "local_cache_size" in stats
        assert stats["local_cache_size"] >= 1
    asyncio.run(_run())


def test_plan_cache_disabled_maxsize_zero():
    async def _run():
        cache = PlanCacheService(use_redis=False, maxsize=0, ttl=3600)
        await cache.set("goal", {"result": "y"})
        assert await cache.get("goal") is None
    asyncio.run(_run())
