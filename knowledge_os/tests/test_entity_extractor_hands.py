"""Entity extractor must not hit Victoria brain (LOOP-BREAKER residual)."""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "knowledge_os" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


@pytest.fixture
def extractor_mod(monkeypatch):
    monkeypatch.setenv("ENTITY_EXTRACTOR_LLM", "true")
    # Fresh module so circuit-breaker globals reset.
    sys.modules.pop("graphrag.entity_extractor", None)
    sys.modules.pop("app.graphrag.entity_extractor", None)
    try:
        mod = importlib.import_module("graphrag.entity_extractor")
    except ImportError:
        mod = importlib.import_module("app.graphrag.entity_extractor")
    mod._LLM_FAIL_STREAK = 0
    mod._LLM_COOLDOWN_UNTIL = 0.0
    return mod


def test_success_resets_fail_streak(extractor_mod):
    extractor_mod._LLM_FAIL_STREAK = 2
    extractor_mod._llm_note_success()
    assert extractor_mod._LLM_FAIL_STREAK == 0


def test_llm_disabled_uses_regex_only(extractor_mod, monkeypatch):
    monkeypatch.setenv("ENTITY_EXTRACTOR_LLM", "false")
    # Reload availability path uses env at call time
    text = "x" * 400 + " Docker Redis `@file.py`"
    ext = extractor_mod.EntityExtractor()

    async def _boom(*_a, **_k):
        raise AssertionError("hands LLM must not be called when ENTITY_EXTRACTOR_LLM=false")

    with patch.object(ext, "_extract_via_hands", new=_boom):
        ents = asyncio.run(ext.extract_entities(text))
    names = {e.name for e in ents}
    assert "Docker" in names or "Redis" in names or "file.py" in names


def test_hands_path_parses_json(extractor_mod):
    ext = extractor_mod.EntityExtractor()

    async def _fake_hands(text: str):
        return [
            extractor_mod.Entity(
                name="Ollama", type="tech", confidence=0.9, metadata={"source": "llm_hands"}
            )
        ]

    long = "y" * 400
    with patch.object(ext, "_extract_via_hands", new=_fake_hands):
        ents = asyncio.run(ext.extract_entities(long))
    assert any(e.name == "Ollama" and e.metadata.get("source") == "llm_hands" for e in ents)


def test_no_run_smart_agent_in_source():
    text = (APP / "graphrag" / "entity_extractor.py").read_text(encoding="utf-8")
    # No live import/call of brain smart-agent (comment-only mentions OK if absent).
    assert "from app.ai_core import" not in text
    assert "OLLAMA_HANDS_URL" in text
    assert "_llm_note_success" in text
    assert "_extract_via_hands" in text
