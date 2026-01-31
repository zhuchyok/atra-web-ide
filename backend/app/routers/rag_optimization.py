"""
Эндпоинты мониторинга оптимизаций RAG-light (Фаза 3, день 3–4).
"""
from fastapi import APIRouter
from typing import Any, Dict

from app.config import get_settings
from app.services.rag_light import get_rag_light_service

router = APIRouter(tags=["rag-optimization"])


@router.get("/stats")
async def get_rag_optimization_stats() -> Dict[str, Any]:
    """Статистика оптимизаций RAG-light."""
    service = get_rag_light_service()
    stats: Dict[str, Any] = {
        "embedding_batch": {},
        "prefetch": {},
        "fallback": {},
    }
    if service.embedding_batch_processor:
        stats["embedding_batch"] = await service.embedding_batch_processor.stats()
    if service.prefetch_service:
        stats["prefetch"] = service.prefetch_service.get_stats()
    if service.fallback_service:
        stats["fallback"] = service.fallback_service.get_stats()
    return stats


@router.post("/prefetch/reload")
async def reload_prefetch() -> Dict[str, Any]:
    """Перезагрузка предзагруженных запросов."""
    service = get_rag_light_service()
    if not service.prefetch_service:
        return {"error": "Prefetch service not available"}
    settings = get_settings()
    max_q = getattr(settings, "rag_light_prefetch_max_queries", 50)
    await service.prefetch_service.load_frequent_queries(max_queries=max_q)
    return {"status": "success", "message": "Prefetch reloaded"}


@router.post("/cache/clear")
async def clear_embedding_cache() -> Dict[str, Any]:
    """Очистка кэша эмбеддингов (батч-процессора)."""
    service = get_rag_light_service()
    if service.embedding_batch_processor:
        service.embedding_batch_processor.clear_cache()
    return {"status": "success", "message": "Embedding cache cleared"}
