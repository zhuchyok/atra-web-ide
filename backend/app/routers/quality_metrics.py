"""
Фаза 4, День 4: API метрик качества RAG.

История валидаций, сводка по метрикам, пороги.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from app.services.knowledge_os import KnowledgeOSClient, get_knowledge_os_client

router = APIRouter(prefix="/api/quality", tags=["quality"])


def _validation_results_dir() -> Path:
    """Каталог validation_results относительно backend."""
    return Path(__file__).resolve().parent.parent.parent / "validation_results"


@router.get("/metrics/history")
async def get_quality_history(days: int = 7) -> Dict[str, Any]:
    """История метрик качества за последние N дней."""
    results_dir = _validation_results_dir()
    if not results_dir.exists():
        return {"history": [], "days_analyzed": days}

    history: List[Dict] = []
    cutoff_date = datetime.now() - timedelta(days=days)

    for result_file in sorted(results_dir.glob("validation_*.json")):
        try:
            with open(result_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            ts = data.get("timestamp", "")
            if not ts:
                continue
            try:
                file_date = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                file_date = datetime.fromisoformat(ts.split(".")[0])
            if file_date.replace(tzinfo=None) >= cutoff_date.replace(tzinfo=None):
                summary = data.get("summary", {})
                history.append({
                    "date": ts,
                    "metrics": data.get("avg_metrics", {}),
                    "total_queries": summary.get("total_queries", 0),
                })
        except Exception:
            continue

    return {
        "history": sorted(history, key=lambda x: x["date"], reverse=True),
        "days_analyzed": days,
    }


@router.get("/metrics/summary")
async def get_quality_summary(
    knowledge_os: KnowledgeOSClient = Depends(get_knowledge_os_client),
) -> Dict[str, Any]:
    """Сводка текущего состояния качества (быстрая валидация на 10 запросах)."""
    try:
        from app.services.validation_pipeline import ValidationPipeline
        from app.services.rag_light import get_rag_light_service
        from app.evaluation.rag_evaluator import RAGEvaluator
    except ImportError as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }

    rag_service = get_rag_light_service(knowledge_os)
    evaluator = RAGEvaluator()

    pipeline = ValidationPipeline(
        validation_path="data/validation_queries.json",
        rag_service=rag_service,
        evaluator=evaluator,
    )

    try:
        results = await pipeline.run_validation(sample_size=10)
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }

    return {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "metrics": results.get("avg_metrics", {}),
        "sample_size": results.get("sample_size", 0),
        "thresholds": {
            "faithfulness": 0.8,
            "relevance": 0.85,
            "coherence": 0.8,
        },
    }
