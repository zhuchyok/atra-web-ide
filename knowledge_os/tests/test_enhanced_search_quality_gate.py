"""KISS RAG quality gates: min_sim, NaN/poison, task_id bleed, empty injection."""

import math

import pytest


def test_filter_drops_nan_and_inf():
    from app.enhanced_search import filter_search_results

    rows = [
        {"id": 1, "content": "good", "similarity": 0.9, "metadata": {}},
        {"id": 2, "content": "nan", "similarity": float("nan"), "metadata": {}},
        {"id": 3, "content": "inf", "similarity": float("inf"), "metadata": {}},
    ]
    out = filter_search_results(rows, min_sim=0.45)
    assert len(out) == 1
    assert out[0]["id"] == 1
    assert math.isfinite(out[0]["similarity"])


def test_filter_drops_below_min_sim(monkeypatch):
    monkeypatch.setenv("RAG_MIN_SIMILARITY", "0.45")
    from app.enhanced_search import filter_search_results

    rows = [
        {"id": 1, "content": "weak", "similarity": 0.2, "metadata": {}},
        {"id": 2, "content": "ok", "similarity": 0.5, "metadata": {}},
    ]
    out = filter_search_results(rows)
    assert [r["id"] for r in out] == [2]


def test_filter_drops_task_id_artifacts():
    from app.enhanced_search import filter_search_results

    rows = [
        {
            "id": 1,
            "content": "worker dump",
            "similarity": 0.99,
            "metadata": {"task_id": "abc-123"},
        },
        {"id": 2, "content": "real doc", "similarity": 0.7, "metadata": {"source": "docs"}},
    ]
    out = filter_search_results(rows, min_sim=0.45)
    assert [r["id"] for r in out] == [2]


def test_filter_drops_curator_finding_nodes():
    """#66: curator_finding refusals must not re-poison Omni-RAG chat context."""
    from app.enhanced_search import filter_search_results

    rows = [
        {
            "id": 1,
            "content": "Когнитивный Код: не могу приступить — INSUFFICIENT_CONTEXT / UNVERIFIED",
            "similarity": 0.95,
            "metadata": {"node_type": "curator_finding", "report": "curator_x.json"},
        },
        {
            "id": 2,
            "content": "standard: brain on 11434 victoria-qwen38",
            "similarity": 0.8,
            "metadata": {"node_type": "standard"},
        },
        {
            "id": 3,
            "content": "plain doc without node_type",
            "similarity": 0.7,
            "metadata": {"source": "docs"},
        },
    ]
    out = filter_search_results(rows, min_sim=0.45)
    assert [r["id"] for r in out] == [2, 3]


def test_filter_skips_min_sim_for_bm25_rows():
    from app.enhanced_search import filter_search_results

    rows = [{"id": 1, "content": "bm25 hit", "similarity": 0.05, "metadata": {}}]
    out = filter_search_results(rows, apply_min_sim=False)
    assert len(out) == 1


def test_format_result_text_empty_when_no_hits():
    from app.enhanced_search import format_result_text

    assert format_result_text("hybrid", []) == ""


def test_format_result_text_uses_longer_snippet():
    from app.enhanced_search import format_result_text

    content = "A" * 600
    text = format_result_text(
        "hybrid", [{"content": content, "similarity": 0.8}], snippet_chars=500
    )
    assert "No relevant knowledge" not in text
    assert "[hybrid sim=0.80]" in text
    assert len(text) > 400


def test_rag_context_usable_rejects_placeholder_and_empty():
    from app.enhanced_search import rag_context_usable

    assert rag_context_usable(None) is False
    assert rag_context_usable({}) is False
    assert (
        rag_context_usable({"results": [], "result_text": "No relevant knowledge found."}) is False
    )
    assert rag_context_usable({"results": [{"id": 1}], "result_text": ""}) is False
    assert (
        rag_context_usable(
            {
                "results": [{"id": 1, "content": "x"}],
                "result_text": "[hybrid sim=0.70] real knowledge",
            }
        )
        is True
    )


def test_embed_fallback_url_defaults_to_hands_not_brain(monkeypatch):
    """nomic must not load onto brain 11434 (contract: hands 11437)."""
    monkeypatch.delenv("LIVE_OLLAMA_URL", raising=False)
    monkeypatch.delenv("OLLAMA_EMBED_URL", raising=False)
    monkeypatch.delenv("OLLAMA_HANDS_URL", raising=False)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    from app.enhanced_search import _embed_fallback_url

    url = _embed_fallback_url()
    assert url == "http://127.0.0.1:11437/api/embeddings"
    assert "11434" not in url


def test_embed_fallback_url_prefers_live_over_embed(monkeypatch):
    monkeypatch.setenv("LIVE_OLLAMA_URL", "http://127.0.0.1:11437")
    monkeypatch.setenv("OLLAMA_EMBED_URL", "http://embed.example:9999")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    from app.enhanced_search import _embed_fallback_url

    assert _embed_fallback_url() == "http://127.0.0.1:11437/api/embeddings"


@pytest.mark.asyncio
async def test_collective_memory_falls_back_when_session_weak(monkeypatch):
    from app.collective_memory import CollectiveMemory

    cm = CollectiveMemory(agent_name="test")
    # Zero token overlap with query → score 0 → must hit knowledge_nodes fallback.
    await cm.store_knowledge("noise", "zzzz unrelated blob")

    async def _fake_kb(query, limit=5):
        return [{"key": "knowledge_base", "value": "ports 11434 brain", "metadata": {}}]

    monkeypatch.setattr(cm, "query_knowledge_base", _fake_kb)
    out = await cm.query_knowledge("что на порту 11434")
    assert out
    assert any("11434" in str(r.get("value", "")) for r in out)
