"""
Эндпоинты latency (Фаза 4.1).
Цель: P95 < 300ms для режима Ask.
"""
import json
from pathlib import Path
from fastapi import APIRouter

router = APIRouter(prefix="/api/latency", tags=["latency"])

# backend/app/routers/latency.py -> repo root
BENCHMARK_PATH = Path(__file__).resolve().parent.parent.parent.parent / "latency_benchmark.json"


@router.get("/benchmark")
async def get_latency_benchmark():
    """
    Последние результаты бенчмарка (из scripts/benchmark_latency.py).
    Запуск: python scripts/benchmark_latency.py
    """
    if not BENCHMARK_PATH.exists():
        return {
            "status": "no_data",
            "message": "Run: python scripts/benchmark_latency.py",
        }
    try:
        with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "status": "ok",
            "p50_ms": data.get("p50_ms"),
            "p95_ms": data.get("p95_ms"),
            "p99_ms": data.get("p99_ms"),
            "avg_ms": data.get("avg_ms"),
            "n_requests": data.get("n_requests"),
            "p95_ok": data.get("p95_ms", 999) < 300,
            "services": data.get("services", {}),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
