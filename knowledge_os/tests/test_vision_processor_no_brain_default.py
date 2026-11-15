"""Vision Ollama must never default to brain :11434 (MASTER: qwen38-only)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
KOS = ROOT / "knowledge_os"
APP = KOS / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def _reload_vision(monkeypatch, *, vision_url: str | None = None):
    monkeypatch.delenv("OLLAMA_VISION_URL", raising=False)
    monkeypatch.delenv("MAC_LLM_URL", raising=False)
    monkeypatch.delenv("SERVER_LLM_URL", raising=False)
    if vision_url is not None:
        monkeypatch.setenv("OLLAMA_VISION_URL", vision_url)
    if "vision_processor" in sys.modules:
        return importlib.reload(sys.modules["vision_processor"])
    import vision_processor as vp

    return vp


def test_resolve_unset_fail_closed_no_11434(monkeypatch):
    vp = _reload_vision(monkeypatch)
    assert vp._resolve_ollama_vision_base() is None
    assert vp.OLLAMA_VISION_URL is None
    assert vp.MAC_LLM_URL is None
    assert vp.SERVER_LLM_URL is None


def test_fallback_nodes_empty_when_vision_url_unset(monkeypatch):
    vp = _reload_vision(monkeypatch)
    proc = vp.VisionProcessor()
    assert proc.fallback_nodes == []


def test_fallback_nodes_use_explicit_vision_url(monkeypatch):
    vp = _reload_vision(monkeypatch, vision_url="http://host.docker.internal:11438")
    proc = vp.VisionProcessor()
    assert len(proc.fallback_nodes) == 1
    assert proc.fallback_nodes[0]["url"] == "http://host.docker.internal:11438"
    assert ":11434" not in proc.fallback_nodes[0]["url"]


def test_source_has_no_hardcoded_brain_ollama_url():
    text = (APP / "vision_processor.py").read_text(encoding="utf-8")
    assert "host.docker.internal:11434" not in text
    assert 'os.getenv("MAC_LLM_URL", "http://localhost:11434")' not in text
    assert 'os.getenv("SERVER_LLM_URL", "http://localhost:11434")' not in text
    # Choice (c) documented
    assert "OLLAMA_VISION_URL" in text
    assert "fail-closed" in text.lower() or "fail-closed" in text


@pytest.mark.asyncio
async def test_process_ollama_fallback_skips_when_no_nodes(monkeypatch):
    vp = _reload_vision(monkeypatch)
    proc = vp.VisionProcessor()
    assert proc.fallback_nodes == []
    out = await proc._process_with_ollama_fallback("dGVzdA==", "describe")
    assert out is None
