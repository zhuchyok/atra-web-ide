"""
Эндпоинты A/B тестирования (День 6–7, Фаза 3).
"""
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.ab_testing import (
    ABTestingService,
    ExperimentConfig,
    get_ab_testing_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ab-testing"])


class ExperimentRequest(BaseModel):
    """Запрос на создание эксперимента."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    variants: Dict[str, float] = Field(default_factory=lambda: {"control": 50, "variant_a": 50})
    parameters: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    enabled: bool = True


@router.get("/experiments")
async def list_experiments(
    ab_testing: ABTestingService = Depends(get_ab_testing_service),
) -> List[Dict[str, Any]]:
    """Список всех экспериментов."""
    experiments = []
    for name, exp in ab_testing.experiments.items():
        experiments.append({
            "name": name,
            "description": exp.description,
            "enabled": exp.enabled,
            "variants": exp.variants,
            "parameters": exp.parameters,
            "start_date": exp.start_date.isoformat() if exp.start_date else None,
            "end_date": exp.end_date.isoformat() if exp.end_date else None,
        })
    return experiments


@router.post("/experiments")
async def create_experiment(
    request: ExperimentRequest,
    ab_testing: ABTestingService = Depends(get_ab_testing_service),
) -> Dict[str, str]:
    """Создание нового эксперимента."""
    exp = ExperimentConfig(
        name=request.name,
        description=request.description,
        variants=request.variants,
        parameters=request.parameters,
        enabled=request.enabled,
    )
    ab_testing.experiments[request.name] = exp
    return {"status": "success", "experiment": request.name}


@router.get("/experiments/{experiment_name}/stats")
async def get_experiment_stats(
    experiment_name: str,
    ab_testing: ABTestingService = Depends(get_ab_testing_service),
) -> Dict[str, Any]:
    """Статистика по эксперименту."""
    stats = ab_testing.get_experiment_stats(experiment_name)
    if not stats:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return stats


@router.post("/experiments/{experiment_name}/toggle")
async def toggle_experiment(
    experiment_name: str,
    enabled: bool = True,
    ab_testing: ABTestingService = Depends(get_ab_testing_service),
) -> Dict[str, Any]:
    """Включение/выключение эксперимента (enabled — query param)."""
    if experiment_name not in ab_testing.experiments:
        raise HTTPException(status_code=404, detail="Experiment not found")
    ab_testing.experiments[experiment_name].enabled = enabled
    return {"status": "success", "enabled": enabled}


@router.get("/user/{user_id}/variants")
async def get_user_variants(
    user_id: str,
    ab_testing: ABTestingService = Depends(get_ab_testing_service),
) -> Dict[str, Any]:
    """Варианты экспериментов для пользователя."""
    variants = {}
    for exp_name in ab_testing.experiments:
        variant = ab_testing.get_variant(user_id, exp_name)
        if variant:
            variants[exp_name] = variant
    return {"user_id": user_id, "variants": variants}
