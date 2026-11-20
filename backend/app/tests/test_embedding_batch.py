"""
Тесты батчинга эмбеддингов (Фаза 3, день 3–4).
Запуск: cd backend && python -m pytest app/tests/test_embedding_batch.py -v

Contract: nomic embeds live on hands :11437 — never teach brain :11434 here.
"""

import asyncio
from unittest.mock import AsyncMock, patch

from app.services.embedding_batch import EmbeddingBatchProcessor

_HANDS = "http://127.0.0.1:11437"


def test_embedding_batch_cache():
    """Кэш и очистка кэша; processor holds hands URL for nomic."""

    async def _run():
        with patch.object(
            EmbeddingBatchProcessor,
            "_call_ollama_single",
            new_callable=AsyncMock,
            return_value=[0.1, 0.2, 0.3],
        ):
            proc = EmbeddingBatchProcessor(
                ollama_url=_HANDS,
                ollama_model="nomic-embed-text",
                batch_size=5,
                batch_timeout_ms=50,
            )
            assert "11437" in proc.ollama_url
            assert "11434" not in proc.ollama_url
            emb = await proc.get_embedding("test query")
            assert emb is not None
            assert emb == [0.1, 0.2, 0.3]
            proc.clear_cache()
            assert len(proc.results_cache) == 0

    asyncio.run(_run())


def test_embedding_batch_stats():
    """Статистика процессора; URL stays on hands slot."""

    async def _run():
        proc = EmbeddingBatchProcessor(
            ollama_url=_HANDS,
            ollama_model="nomic-embed-text",
            batch_size=10,
            batch_timeout_ms=50,
        )
        assert "11434" not in proc.ollama_url
        stats = await proc.stats()
        assert "queue_size" in stats
        assert "cache_size" in stats
        assert stats["batch_size"] == 10

    asyncio.run(_run())


def test_embedding_batch_posts_to_hands_not_brain():
    """_call_ollama_single must POST nomic to hands /api/embeddings, not brain."""
    posted: dict = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"embedding": [0.5, 0.6]}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            posted["url"] = url
            posted["json"] = json
            return _Resp()

    async def _run():
        with patch("app.services.embedding_batch.httpx.AsyncClient", _Client):
            proc = EmbeddingBatchProcessor(
                ollama_url=_HANDS,
                ollama_model="nomic-embed-text",
            )
            emb = await proc._call_ollama_single("hello")
            assert emb == [0.5, 0.6]

    asyncio.run(_run())
    assert posted["url"] == f"{_HANDS}/api/embeddings"
    assert "11434" not in posted["url"]
    assert posted["json"]["model"] == "nomic-embed-text"


def test_embedding_batch_ctor_strips_full_embeddings_url():
    """Ctor with .../api/embeddings must still POST once to /api/embeddings (no double-append)."""
    posted: dict = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"embedding": [0.1]}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            posted["url"] = url
            return _Resp()

    async def _run():
        with patch("app.services.embedding_batch.httpx.AsyncClient", _Client):
            proc = EmbeddingBatchProcessor(
                ollama_url=f"{_HANDS}/api/embeddings",
                ollama_model="nomic-embed-text",
            )
            assert proc.ollama_url == _HANDS
            emb = await proc._call_ollama_single("hello")
            assert emb == [0.1]

    asyncio.run(_run())
    assert posted["url"] == f"{_HANDS}/api/embeddings"
    assert posted["url"].count("/api/embeddings") == 1
