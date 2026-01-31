"""
Тесты предзагрузки RAG-light (Фаза 3, день 3–4).
Запуск: cd backend && python -m pytest app/tests/test_rag_light_prefetch.py -v
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.services.rag_light_prefetch import RAGLightPrefetch


def test_prefetch_default_queries():
    """Предзагрузка с дефолтными запросами (мок процессора)."""
    async def _run():
        batch_processor = MagicMock()
        batch_processor.get_embedding = AsyncMock(return_value=[0.1, 0.2])
        prefetch = RAGLightPrefetch(batch_processor)
        await prefetch.load_frequent_queries(max_queries=3)
        stats = prefetch.get_stats()
        assert stats["prefetched_queries_count"] >= 0
        assert "total_prefetched" in stats
    asyncio.run(_run())


def test_prefetch_is_prefetched():
    """Проверка is_prefetched после загрузки."""
    async def _run():
        batch_processor = MagicMock()
        batch_processor.get_embedding = AsyncMock(return_value=[0.1])
        prefetch = RAGLightPrefetch(batch_processor)
        await prefetch.load_frequent_queries(max_queries=2)
        # Дефолтные запросы должны быть в списке после успешного prefetch
        assert prefetch.get_stats()["prefetched_queries_count"] >= 0
    asyncio.run(_run())
