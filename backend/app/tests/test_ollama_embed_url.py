"""Guards: backend embeds default to hands nomic (:11437), not brain (:11434)."""

import asyncio
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_REPO = Path(__file__).resolve().parents[3]


def test_resolve_ollama_embed_base_defaults_to_hands(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("LIVE_OLLAMA_URL", raising=False)
    monkeypatch.delenv("OLLAMA_EMBED_URL", raising=False)
    monkeypatch.delenv("OLLAMA_HANDS_URL", raising=False)
    # Brain URL must not hijack embeds.
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11434")

    from app.config import resolve_ollama_embed_base_url

    assert resolve_ollama_embed_base_url() == "http://127.0.0.1:11437"


def test_resolve_ollama_embed_prefers_live_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LIVE_OLLAMA_URL", "http://127.0.0.1:11437")
    monkeypatch.setenv("OLLAMA_EMBED_URL", "http://embed.example:9999")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

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


def test_vector_core_default_embed_url_is_hands_not_brain():
    """vector-core used to default OLLAMA_URL to :11434 (no nomic on brain)."""
    text = (_REPO / "infrastructure/docker/vector-core/main.py").read_text(encoding="utf-8")
    assert 'getenv("OLLAMA_URL", "http://host.docker.internal:11434")' not in text
    assert "LIVE_OLLAMA_URL" in text
    assert "11437" in text
    # Default base must mention hands port, never brain as getenv default.
    assert re.search(r'_default_embed_base\s*=\s*\([\s\S]*?11437', text)


def test_mass_and_seed_scripts_do_not_fallback_to_brain_base_url():
    mass = (_REPO / "scripts/mass_embedding_generator.py").read_text(encoding="utf-8")
    seed = (_REPO / "scripts/seed_knowledge_from_dataset.py").read_text(encoding="utf-8")
    for text in (mass, seed):
        assert 'getenv("OLLAMA_BASE_URL"' not in text
        assert 'environ.get("OLLAMA_BASE_URL"' not in text
        assert 'environ.get("OLLAMA_URL"' not in text
        assert "11437" in text


def test_seed_validation_answers_strips_embed_path_and_ignores_brain(
    monkeypatch: pytest.MonkeyPatch,
):
    """Compose sets OLLAMA_EMBED_URL=.../api/embeddings; must not double-append."""
    text = (_REPO / "scripts/seed_validation_answers.py").read_text(encoding="utf-8")
    assert "resolve_ollama_embed_base_url" in text
    assert 'f"{_embed_url}/api/embeddings"' not in text

    monkeypatch.setenv(
        "OLLAMA_EMBED_URL", "http://host.docker.internal:11437/api/embeddings"
    )
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.delenv("LIVE_OLLAMA_URL", raising=False)

    from app.config import resolve_ollama_embed_base_url

    base = resolve_ollama_embed_base_url()
    assert base == "http://host.docker.internal:11437"
    assert "11434" not in base
    assert not base.endswith("/api/embeddings")
    assert f"{base.rstrip('/')}/api/embeddings" == (
        "http://host.docker.internal:11437/api/embeddings"
    )
