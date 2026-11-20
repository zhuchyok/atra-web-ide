"""Guards: backend embeds default to hands nomic (:11437), not brain (:11434)."""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def test_resolve_ollama_embed_base_defaults_to_hands(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OLLAMA_EMBED_URL", raising=False)
    monkeypatch.delenv("OLLAMA_HANDS_URL", raising=False)
    # Brain URL must not hijack embeds.
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11434")

    from app.config import resolve_ollama_embed_base_url

    assert resolve_ollama_embed_base_url() == "http://127.0.0.1:11437"


def test_resolve_ollama_embed_prefers_explicit_and_strips_path(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "OLLAMA_EMBED_URL", "http://embed.example:9999/api/embeddings"
    )
    monkeypatch.setenv("OLLAMA_HANDS_URL", "http://127.0.0.1:11437")

    from app.config import resolve_ollama_embed_base_url

    assert resolve_ollama_embed_base_url() == "http://embed.example:9999"


def test_rag_light_embed_base_ignores_brain_ollama_url():
    from app.services.rag_light import _embed_ollama_base

    settings = SimpleNamespace(
        ollama_url="http://127.0.0.1:11434",
        ollama_embed_url="http://127.0.0.1:11437",
    )
    assert _embed_ollama_base(settings) == "http://127.0.0.1:11437"


def test_rag_light_get_embedding_posts_to_hands_url():
    from app.services.rag_light import RAGLightService

    settings = SimpleNamespace(
        ollama_url="http://127.0.0.1:11434",
        ollama_embed_url="http://127.0.0.1:11437",
        ollama_embed_model="nomic-embed-text",
    )
    posted: dict = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"embedding": [0.1, 0.2]}

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
        with (
            patch("app.services.rag_light.get_settings", return_value=settings),
            patch("app.services.rag_light.httpx.AsyncClient", _Client),
        ):
            return await RAGLightService().get_embedding("hello")

    emb = asyncio.run(_run())
    assert emb == [0.1, 0.2]
    assert posted["url"] == "http://127.0.0.1:11437/api/embeddings"
    assert "11434" not in posted["url"]
