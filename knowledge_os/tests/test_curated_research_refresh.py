"""v137: curated AI Research auto-refresh metadata + target rotation."""

from datetime import datetime, timezone

import pytest
from app.curated_research_refresh import refresh_scout
from app.veronica_scout import (
    is_usable_scout_analysis,
    scout_knowledge_payload,
    select_scout_targets,
)


def test_scout_payload_matches_dashboard_filter():
    payload = scout_knowledge_payload(
        {
            "topic": "latest AI research papers 2026",
            "content": "A finding about agents.",
            "sources": ["https://example.com/paper"],
        }
    )
    meta = payload["metadata"]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert payload["domain"] == "AI Research"
    assert meta["source"] == "scout_research"
    assert meta["file_path"].startswith(f"scout/{stamp}-")
    assert meta["file_path"].endswith(".md")
    assert "GLOBAL SCOUT" in payload["content"]
    assert "A finding about agents." in payload["content"]
    assert meta["urls"] == ["https://example.com/paper"]


def test_scout_payload_empty_topic_still_has_file_path():
    payload = scout_knowledge_payload({"topic": "", "content": "x", "sources": []})
    assert payload["metadata"]["file_path"].startswith("scout/")
    assert payload["metadata"]["source"] == "scout_research"


def test_select_scout_targets_rotates_by_day():
    targets = ["a", "b", "c", "d", "e"]
    assert select_scout_targets(targets, 1, day_of_year=0) == ["a"]
    assert select_scout_targets(targets, 1, day_of_year=1) == ["b"]
    assert select_scout_targets(targets, 2, day_of_year=4) == ["e", "a"]
    assert select_scout_targets(targets, 0, day_of_year=3) == []
    assert select_scout_targets([], 1, day_of_year=1) == []


def test_veronica_scout_class_is_importable():
    from app.veronica_scout import VeronicaScout

    assert callable(VeronicaScout)
    assert hasattr(VeronicaScout, "run_scouting_cycle")


def test_usable_scout_analysis_rejects_error_stubs():
    assert is_usable_scout_analysis("❌ Ошибка: ") is False
    assert is_usable_scout_analysis("short") is False
    assert is_usable_scout_analysis("❌ Нет доступных локальных моделей") is False
    assert (
        is_usable_scout_analysis(
            "World-class agent architectures in 2026 emphasize tool use, memory, and verification loops. "
            "Production systems keep a planner separate from executors."
        )
        is True
    )


@pytest.mark.asyncio
async def test_visual_index_disabled(monkeypatch):
    monkeypatch.setenv("NIGHTLY_VISUAL_INDEX_ENABLED", "false")
    from app.curated_research_refresh import refresh_visual_index

    assert await refresh_visual_index() == 0


@pytest.mark.asyncio
async def test_visual_index_posts_text_content(monkeypatch, tmp_path):
    monkeypatch.setenv("NIGHTLY_VISUAL_INDEX_ENABLED", "true")
    monkeypatch.setenv("CURATED_DOCS_DIR", str(tmp_path))
    monkeypatch.setenv("VISUAL_SEARCH_URL", "http://visual.test")
    (tmp_path / "COGNITIVE_CODE.md").write_text("first principles and five whys " * 8)
    (tmp_path / "README.md").write_text("extra markdown " * 8)

    posted = []

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            assert url.endswith("/health")
            return _Resp()

        async def post(self, url, json):
            posted.append(json)
            return _Resp()

    monkeypatch.setattr("httpx.AsyncClient", _Client)
    from app.curated_research_refresh import refresh_visual_index

    assert await refresh_visual_index() == 2
    assert all("text_content" in body and body["text_content"].strip() for body in posted)
    assert posted[0]["file_path"].endswith("COGNITIVE_CODE.md")


@pytest.mark.asyncio
async def test_research_refresh_disabled(monkeypatch):
    monkeypatch.setenv("NIGHTLY_RESEARCH_SCOUT_ENABLED", "false")
    assert await refresh_scout() == 0
