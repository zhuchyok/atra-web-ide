import asyncio
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/cost", tags=["cost"])


class CostEntry(BaseModel):
    expert_id: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    cost_usd: float
    timestamp: Optional[int] = None


class CostSummary(BaseModel):
    period: str
    total_cost: float
    total_tokens: int
    by_model: dict
    by_expert: dict
    trend: list


class BudgetAlert(BaseModel):
    threshold: float
    percentage: float
    expert_id: Optional[str] = None


_cost_store: list[CostEntry] = []
_budgets: dict[str, float] = {}
_alerts: list[BudgetAlert] = []


PRICING = {
    "llama-3.1-8b": {"input": 0.0, "output": 0.0},
    "llama-3.1-70b": {"input": 0.0008, "output": 0.0008},
    "qwen-2.5-72b": {"input": 0.0009, "output": 0.0009},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "default": {"input": 0.001, "output": 0.005},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = PRICING.get(model, PRICING["default"])
    return (
        input_tokens / 1_000_000 * pricing["input"] + output_tokens / 1_000_000 * pricing["output"]
    )


def _get_period_start(period: str) -> datetime:
    now = datetime.now()
    if period == "24h":
        return now - timedelta(hours=24)
    elif period == "7d":
        return now - timedelta(days=7)
    elif period == "30d":
        return now - timedelta(days=30)
    elif period == "1h":
        return now - timedelta(hours=1)
    return now - timedelta(days=7)


@router.post("/track")
async def track_cost(entry: CostEntry):
    entry.timestamp = entry.timestamp or int(datetime.now().timestamp())
    _cost_store.append(entry)
    await _check_budget_alerts(entry)
    return {"id": str(uuid.uuid4()), "status": "recorded"}


@router.post("/track/batch")
async def track_cost_batch(entries: list[CostEntry]):
    now = int(datetime.now().timestamp())
    recorded = []
    for entry in entries:
        entry.timestamp = entry.timestamp or now
        _cost_store.append(entry)
        recorded.append(entry)
        await _check_budget_alerts(entry)
    return {"recorded": len(recorded)}


async def _check_budget_alerts(entry: CostEntry):
    budget_key = entry.expert_id or "global"
    budget = _budgets.get(budget_key, float("inf"))
    if budget == float("inf"):
        return

    period_start = _get_period_start("24h")
    period_entries = [
        e
        for e in _cost_store
        if e.expert_id == entry.expert_id and datetime.fromtimestamp(e.timestamp) >= period_start
    ]
    total = sum(e.cost_usd for e in period_entries)
    percentage = (total / budget) * 100 if budget > 0 else 0

    if percentage >= 80:
        alert = BudgetAlert(threshold=budget, percentage=percentage, expert_id=entry.expert_id)
        _alerts.append(alert)
        asyncio.create_task(_send_budget_alert(alert))


async def _send_budget_alert(alert: BudgetAlert):
    print(f"BUDGET ALERT: {alert.percentage:.1f}% of ${alert.threshold} used for {alert.expert_id}")


@router.get("/summary", response_model=CostSummary)
async def get_cost_summary(period: str = Query("7d", regex="^(24h|7d|30d|1h)$")):
    period_start = _get_period_start(period)

    filtered = [e for e in _cost_store if datetime.fromtimestamp(e.timestamp) >= period_start]

    total_cost = sum(e.cost_usd for e in filtered)
    total_tokens = sum(e.input_tokens + e.output_tokens for e in filtered)

    by_model = defaultdict(float)
    by_expert = defaultdict(float)

    for e in filtered:
        by_model[e.model] += e.cost_usd
        by_expert[e.expert_id] += e.cost_usd

    trend = _calculate_trend(filtered)

    return CostSummary(
        period=period,
        total_cost=total_cost,
        total_tokens=total_tokens,
        by_model=dict(by_model),
        by_expert=dict(by_expert),
        trend=trend,
    )


def _calculate_trend(entries: list[CostEntry]) -> list[dict]:
    if not entries:
        return []

    daily = defaultdict(float)
    for e in entries:
        day = datetime.fromtimestamp(e.timestamp).date().isoformat()
        daily[day] += e.cost_usd

    sorted_days = sorted(daily.items())[-7:]
    return [{"date": d, "cost": c} for d, c in sorted_days]


@router.get("/by-expert/{expert_id}")
async def get_cost_by_expert(expert_id: str, period: str = Query("7d", regex="^(24h|7d|30d|1h)$")):
    period_start = _get_period_start(period)

    filtered = [
        e
        for e in _cost_store
        if e.expert_id == expert_id and datetime.fromtimestamp(e.timestamp) >= period_start
    ]

    total_cost = sum(e.cost_usd for e in filtered)
    total_tokens = sum(e.input_tokens + e.output_tokens for e in filtered)
    avg_duration = sum(e.duration_ms for e in filtered) / len(filtered) if filtered else 0

    by_model = defaultdict(lambda: {"cost": 0, "tokens": 0})
    for e in filtered:
        by_model[e.model]["cost"] += e.cost_usd
        by_model[e.model]["tokens"] += e.input_tokens + e.output_tokens

    return {
        "expert_id": expert_id,
        "period": period,
        "total_cost": total_cost,
        "total_tokens": total_tokens,
        "avg_duration_ms": avg_duration,
        "by_model": dict(by_model),
        "request_count": len(filtered),
    }


@router.get("/leaderboard")
async def get_cost_leaderboard(
    period: str = Query("7d", regex="^(24h|7d|30d|1h)$"), limit: int = 10
):
    period_start = _get_period_start(period)

    filtered = [e for e in _cost_store if datetime.fromtimestamp(e.timestamp) >= period_start]

    by_expert = defaultdict(lambda: {"cost": 0, "tokens": 0, "requests": 0})
    for e in filtered:
        by_expert[e.expert_id]["cost"] += e.cost_usd
        by_expert[e.expert_id]["tokens"] += e.input_tokens + e.output_tokens
        by_expert[e.expert_id]["requests"] += 1

    leaderboard = sorted(
        [
            {"expert_id": expert_id, **stats, "avg_cost": stats["cost"] / stats["requests"]}
            for expert_id, stats in by_expert.items()
        ],
        key=lambda x: x["cost"],
        reverse=True,
    )[:limit]

    return leaderboard


@router.post("/budget")
async def set_budget(expert_id: str, budget: float, period: str = "24h"):
    _budgets[expert_id] = budget
    return {"expert_id": expert_id, "budget": budget, "period": period}


@router.get("/budget/{expert_id}")
async def get_budget(expert_id: str):
    if expert_id not in _budgets:
        raise HTTPException(status_code=404, detail="Budget not set")

    budget = _budgets[expert_id]
    period_start = _get_period_start("24h")

    spent = sum(
        e.cost_usd
        for e in _cost_store
        if e.expert_id == expert_id and datetime.fromtimestamp(e.timestamp) >= period_start
    )

    return {
        "expert_id": expert_id,
        "budget": budget,
        "spent": spent,
        "remaining": budget - spent,
        "percentage": (spent / budget * 100) if budget > 0 else 0,
    }


@router.get("/budgets")
async def list_budgets():
    return [{"expert_id": k, "budget": v} for k, v in _budgets.items()]


@router.get("/alerts")
async def get_alerts(limit: int = 20):
    return _alerts[-limit:]


@router.post("/optimize")
async def get_cost_optimization(model: str = Query("llama-3.1-8b")):
    period_start = _get_period_start("7d")

    filtered = [
        e
        for e in _cost_store
        if e.model == model and datetime.fromtimestamp(e.timestamp) >= period_start
    ]

    total_cost = sum(e.cost_usd for e in filtered)
    total_tokens = sum(e.input_tokens + e.output_tokens for e in filtered)

    avg_tokens_per_req = total_tokens / len(filtered) if filtered else 0
    potential_savings = 0

    if avg_tokens_per_req > 2000:
        potential_savings = total_cost * 0.3

    recommendations = []
    if avg_tokens_per_req > 5000:
        recommendations.append("Consider using smaller model for simple queries")
    if total_cost > 100:
        recommendations.append("Implement caching for repeated queries")
    if len(filtered) > 1000:
        recommendations.append("Enable batch processing for bulk tasks")

    return {
        "model": model,
        "period": "7d",
        "total_cost": total_cost,
        "request_count": len(filtered),
        "avg_tokens_per_request": avg_tokens_per_req,
        "potential_savings_usd": potential_savings,
        "recommendations": recommendations,
    }


async def get_cost_tracker() -> dict:
    return {
        "entries_count": len(_cost_store),
        "budgets_count": len(_budgets),
        "alerts_count": len(_alerts),
        "pricing_models": list(PRICING.keys()),
    }
