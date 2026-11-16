"""p95 KISS: ai_core RAG_RERANKER_ENABLED defaults OFF (align victoria RAG_RERANK_ENABLED)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AI_CORE = ROOT / "knowledge_os" / "app" / "ai_core.py"
RAG_RERANKER = ROOT / "knowledge_os" / "app" / "rag_reranker.py"


def test_ai_core_reranker_default_is_false():
    text = AI_CORE.read_text(encoding="utf-8")
    assert 'os.getenv("RAG_RERANKER_ENABLED", "false")' in text
    assert 'os.getenv("RAG_RERANKER_ENABLED", "true")' not in text


def test_rag_reranker_module_default_is_false():
    text = RAG_RERANKER.read_text(encoding="utf-8")
    assert 'os.getenv("RAG_RERANKER_ENABLED", "false")' in text
    assert 'os.getenv("RAG_RERANKER_ENABLED", "true")' not in text


def test_getenv_default_off_behavior(monkeypatch):
    monkeypatch.delenv("RAG_RERANKER_ENABLED", raising=False)
    assert os.getenv("RAG_RERANKER_ENABLED", "false").lower() in ("false", "0", "no", "")
    monkeypatch.setenv("RAG_RERANKER_ENABLED", "true")
    assert os.getenv("RAG_RERANKER_ENABLED", "false").lower() not in ("false", "0", "no", "")
