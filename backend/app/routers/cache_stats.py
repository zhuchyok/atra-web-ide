"""
API мониторинга кэша (RAG Context Cache).
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/cache", tags=["cache"])


@router.get("/stats")
async def get_cache_stats():
    """Статистика RAG Context Cache: hit rate, hits, misses."""
    try:
        from app.services.rag_context_cache import get_cache_monitor
        monitor = get_cache_monitor()
        return {"status": "ok", **monitor.get_stats()}
    except Exception as e:
        return {"status": "error", "message": str(e)}
