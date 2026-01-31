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


@router.get("/metrics/summary")
async def metrics_summary():
    """Человекочитаемая сводка метрик (полные значения — в GET /metrics)."""
    from app.metrics.prometheus_metrics import ACTIVE_REQUESTS

    summary = {
        "info": "Use GET /metrics for full Prometheus exposition format",
        "endpoints": {"metrics": "/metrics", "summary": "/metrics/summary"},
    }

    try:
        # Текущее значение gauge (unlabeled Gauge)
        v = getattr(ACTIVE_REQUESTS, "_value", None)
        summary["active_requests"] = getattr(v, "value", 0) if v is not None else 0
    except Exception:
        summary["active_requests"] = "see /metrics"

    return summary
