"""dialogue_llm: hands phi/nomic → 11437; never POST phi to brain 11434."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
KOS = ROOT / "knowledge_os"
APP = KOS / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_is_hands_dialogue_model_xor_markers():
    from dialogue_llm import is_hands_dialogue_model

    assert is_hands_dialogue_model("phi3.5:3.8b") is True
    assert is_hands_dialogue_model("phi3.5:3.8b-stable") is True
    assert is_hands_dialogue_model("nomic-embed-text:latest") is True
    for name in ("smollm2:360m", "tinyllama:1.1b-chat", "victoria-qwen38:latest"):
        assert is_hands_dialogue_model(name) is False, name


def test_ollama_base_for_dialogue_model_routes_hands(monkeypatch):
    import dialogue_llm as mod

    monkeypatch.setenv("OLLAMA_HANDS_URL", "http://localhost:11437")
    monkeypatch.setattr(mod, "OLLAMA_BASE", "http://localhost:11434")
    monkeypatch.setattr(mod, "OLLAMA_HANDS_BASE", "http://localhost:11437")

    assert mod.ollama_base_for_dialogue_model("phi3.5:3.8b") == "http://localhost:11437"
    assert (
        mod.ollama_base_for_dialogue_model("phi3.5:3.8b-stable")
        == "http://localhost:11437"
    )
    assert mod.ollama_base_for_dialogue_model("smollm2:360m") == "http://localhost:11434"
    assert (
        mod.ollama_base_for_dialogue_model("victoria-qwen38:latest")
        == "http://localhost:11434"
    )


def test_normalize_stable_before_hands_post():
    from dialogue_llm import normalize_ollama_hands_model

    assert normalize_ollama_hands_model("phi3.5:3.8b-stable") == "phi3.5:3.8b"
    assert normalize_ollama_hands_model("phi3.5:3.8b") == "phi3.5:3.8b"


@pytest.mark.asyncio
async def test_try_ollama_posts_phi_to_hands_not_brain(monkeypatch):
    import dialogue_llm as mod

    monkeypatch.setenv("OLLAMA_HANDS_URL", "http://localhost:11437")
    monkeypatch.setenv("DIALOGUE_OLLAMA_BUSY_RETRIES", "1")
    monkeypatch.setenv("DIALOGUE_OLLAMA_MAX_CANDIDATES", "1")
    monkeypatch.setattr(mod, "OLLAMA_BASE", "http://localhost:11434")
    monkeypatch.setattr(mod, "OLLAMA_HANDS_BASE", "http://localhost:11437")
    monkeypatch.setattr(mod, "HTTP_TIMEOUT", 5.0)

    async def _resolve(_hint):
        return "phi3.5:3.8b-stable"

    monkeypatch.setattr(mod, "_resolve_ollama_model", _resolve)

    captured: dict = {}

    class _Resp:
        status_code = 200
        text = ""

        def json(self):
            return {"response": "ok-from-hands"}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            captured["url"] = url
            captured["json"] = json
            return _Resp()

    with patch.object(mod.httpx, "AsyncClient", _Client):
        text, reason = await mod._try_ollama("hello", model_hint="phi3.5:3.8b-stable")

    assert reason == "ok"
    assert text == "ok-from-hands"
    assert captured["url"] == "http://localhost:11437/api/generate"
    assert "11434" not in captured["url"]
    assert captured["json"]["model"] == "phi3.5:3.8b"


@pytest.mark.asyncio
async def test_try_ollama_keeps_non_hands_on_brain(monkeypatch):
    import dialogue_llm as mod

    monkeypatch.setenv("OLLAMA_HANDS_URL", "http://localhost:11437")
    monkeypatch.setenv("DIALOGUE_OLLAMA_BUSY_RETRIES", "1")
    monkeypatch.setenv("DIALOGUE_OLLAMA_MAX_CANDIDATES", "1")
    monkeypatch.setattr(mod, "OLLAMA_BASE", "http://localhost:11434")
    monkeypatch.setattr(mod, "HTTP_TIMEOUT", 5.0)

    async def _resolve(_hint):
        return "smollm2:360m"

    monkeypatch.setattr(mod, "_resolve_ollama_model", _resolve)

    captured: dict = {}

    class _Resp:
        status_code = 200
        text = ""

        def json(self):
            return {"response": "ok-brain"}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            captured["url"] = url
            captured["json"] = json
            return _Resp()

    with patch.object(mod.httpx, "AsyncClient", _Client):
        text, reason = await mod._try_ollama("hello", model_hint="smollm2:360m")

    assert reason == "ok"
    assert text == "ok-brain"
    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["json"]["model"] == "smollm2:360m"
    assert captured["json"]["keep_alive"] == 0


def test_dialogue_llm_source_wires_hands_url():
    text = (APP / "dialogue_llm.py").read_text(encoding="utf-8")
    assert "OLLAMA_HANDS_URL" in text
    assert "normalize_ollama_hands_model" in text
    assert "is_hands_dialogue_model" in text
    assert "ollama_base_for_dialogue_model" in text
    # Brain default remains for non-hands / tags fallback.
    assert "11434" in text
    assert "11437" in text
