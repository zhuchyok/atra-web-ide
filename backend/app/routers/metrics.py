"""
Эндпоинты Prometheus метрик (День 5).
"""
import logging
from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST

from app.metrics.prometheus_metrics import get_metrics

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics_endpoint():
    """Эндпоинт для сбора метрик Prometheus (scrape target)."""
    try:
        metrics_data = get_metrics()
        return Response(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST,
        )
    except Exception as e:
        logger.error("Error generating metrics: %s", e, exc_info=True)
        return Response(
            content=b"",
            media_type=CONTENT_TYPE_LATEST,
            status_code=500,
        )


def _get_expert_fallback_counts():
    """П.4 пушка: текущие значения счётчиков expert vs fallback (для виджета и алертов)."""
    from app.metrics.prometheus_metrics import CHAT_EXPERT_ANSWER_TOTAL, CHAT_FALLBACK_TOTAL
    expert = 0
    try:
        for _labels, child in getattr(CHAT_EXPERT_ANSWER_TOTAL, "_metrics", {}).items():
            v = getattr(child, "_value", None)
            expert += (v.get() if hasattr(v, "get") else 0) or 0
    except Exception:
        pass
    fallback = 0
    try:
        v = getattr(CHAT_FALLBACK_TOTAL, "_value", None)
        fallback = (v.get() if hasattr(v, "get") else 0) or 0
    except Exception:
        pass
    total = expert + fallback
    ratio_fallback = (fallback / total) if total else 0.0
    return expert, fallback, ratio_fallback


@router.get("/metrics/summary")
async def metrics_summary():
    """Человекочитаемая сводка метрик (полные значения — в GET /metrics)."""
    from app.metrics.prometheus_metrics import ACTIVE_REQUESTS

    summary = {
        "info": "Use GET /metrics for full Prometheus exposition format",
        "endpoints": {"metrics": "/metrics", "summary": "/metrics/summary"},
    }

    try:
        v = getattr(ACTIVE_REQUESTS, "_value", None)
        summary["active_requests"] = getattr(v, "value", 0) if v is not None else 0
    except Exception:
        summary["active_requests"] = "see /metrics"

    try:
        expert, fallback, ratio_fallback = _get_expert_fallback_counts()
        summary["chat_expert_answer_total"] = expert
        summary["chat_fallback_total"] = fallback
        summary["chat_fallback_ratio"] = round(ratio_fallback, 4)
        summary["alert_fallback_high"] = ratio_fallback > 0.3  # П.4 пушка: порог 30%
    except Exception:
        summary["chat_expert_answer_total"] = "see /metrics"
        summary["chat_fallback_total"] = "see /metrics"

    return summary
