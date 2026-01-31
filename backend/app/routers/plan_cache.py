"""
Эндпоинты управления кэшем планов (Фаза 3).
"""
from fastapi import APIRouter, Depends
from typing import Optional

from app.services.plan_cache import PlanCacheService, get_plan_cache_service

router = APIRouter(tags=["plan-cache"])


@router.get("/stats")
async def get_cache_stats(
    plan_cache: PlanCacheService = Depends(get_plan_cache_service),
):
    """Статистика кэша планов."""
    return await plan_cache.stats()


@router.post("/clear")
async def clear_cache(
    goal: Optional[str] = None,
    project_context: Optional[str] = None,
    plan_cache: PlanCacheService = Depends(get_plan_cache_service),
):
    """Очистка кэша планов. Без параметров — очистить весь кэш."""
    await plan_cache.clear(goal=goal, project_context=project_context)
    return {"status": "success", "message": "Cache cleared"}
