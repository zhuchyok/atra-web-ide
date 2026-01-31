"""
Тесты батчинга эмбеддингов (Фаза 3, день 3–4).
Запуск: cd backend && python -m pytest app/tests/test_embedding_batch.py -v
"""
import asyncio
from unittest.mock import AsyncMock, patch

from app.services.embedding_batch import EmbeddingBatchProcessor


def test_embedding_batch_cache():
    """Кэш и очистка кэша."""
    async def _run():
        with patch.object(
            EmbeddingBatchProcessor,
            "_call_ollama_single",
            new_callable=AsyncMock,
            return_value=[0.1, 0.2, 0.3],
        ):
            proc = EmbeddingBatchProcessor(
                ollama_url="http://localhost:11434",
                ollama_model="nomic-embed-text",
                batch_size=5,
                batch_timeout_ms=50,
            )
            emb = await proc.get_embedding("test query")
            assert emb is not None
            assert emb == [0.1, 0.2, 0.3]
            proc.clear_cache()
            assert len(proc.results_cache) == 0
    asyncio.run(_run())


def test_embedding_batch_stats():
    """Статистика процессора."""
    async def _run():
        proc = EmbeddingBatchProcessor(
            ollama_url="http://localhost:11434",
            ollama_model="test",
            batch_size=10,
            batch_timeout_ms=50,
        )
        stats = await proc.stats()
        assert "queue_size" in stats
        assert "cache_size" in stats
        assert stats["batch_size"] == 10
    asyncio.run(_run())
