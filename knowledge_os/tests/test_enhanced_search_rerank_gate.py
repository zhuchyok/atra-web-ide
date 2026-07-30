"""Reranker must respect RAG_RERANKER_ENABLED (omni-rag hang fix v134)."""

import os

import pytest


def test_reranker_disabled_by_env(monkeypatch):
    monkeypatch.setenv("RAG_RERANKER_ENABLED", "false")
    from app.enhanced_search import _reranker_enabled

    assert _reranker_enabled() is False


def test_reranker_enabled_by_default(monkeypatch):
    monkeypatch.delenv("RAG_RERANKER_ENABLED", raising=False)
    from app.enhanced_search import _reranker_enabled

    assert _reranker_enabled() is True


@pytest.mark.asyncio
async def test_rerank_results_noop_when_disabled(monkeypatch):
    monkeypatch.setenv("RAG_RERANKER_ENABLED", "false")
    from app.enhanced_search import rerank_results

    rows = [{"content": "a", "similarity": 0.5}, {"content": "b", "similarity": 0.4}]
    out = await rerank_results("q", rows)
    assert out is rows
    assert "rerank_score" not in out[0]
