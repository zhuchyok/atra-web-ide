import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
APP_ROOT = os.path.join(ROOT, "knowledge_os", "app")
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)


class _AcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    async def fetch(self, query, *args):
        if "FROM memory_crystals" in query:
            return self._rows
        return []


class _FakePool:
    def __init__(self, rows):
        self._conn = _FakeConn(rows)

    def acquire(self):
        return _AcquireCtx(self._conn)


@pytest.mark.asyncio
async def test_operational_queries_skip_crystals(monkeypatch):
    from app import ai_pipeline

    called = {"value": False}

    async def _boom():
        called["value"] = True
        raise AssertionError("DB should not be hit for operational crystal skip")

    monkeypatch.setenv("AI_PIPELINE_CRYSTALS_SKIP_OPERATIONAL", "true")
    monkeypatch.setattr("ai_core._get_db_pool", _boom)

    res = await ai_pipeline.load_memory_crystals(
        project_context="atra-web-ide",
        task_category="fast",
        user_prompt="проверь health и таймауты",
    )
    assert res == ""
    assert called["value"] is False


@pytest.mark.asyncio
async def test_crystal_filter_removes_pgbouncer_noise(monkeypatch):
    from app import ai_pipeline

    rows = [
        {"crystal_type": "parameter", "content": "Database Port: 6432 (PgBouncer)"},
        {"crystal_type": "decision", "content": "Use per-task isolation in dynamic pool."},
        {
            "crystal_type": "fact",
            "content": "Принято. Переходим к выполнению ТЗ по PgBouncer.ini default_pool_size",
        },
    ]

    async def _fake_pool():
        return _FakePool(rows)

    monkeypatch.setenv("AI_PIPELINE_CRYSTALS_SKIP_OPERATIONAL", "true")
    monkeypatch.delenv("AI_PIPELINE_CRYSTALS_DENY_REGEX", raising=False)  # use default broadened
    monkeypatch.setenv("AI_PIPELINE_CRYSTALS_ALLOWED_TYPES", "decision,parameter,milestone,fact")
    monkeypatch.setattr("ai_core._get_db_pool", _fake_pool)

    res = await ai_pipeline.load_memory_crystals(
        project_context="atra-web-ide",
        task_category="reasoning",
        user_prompt="Сделай архитектурный анализ изоляции задач с рисками.",
    )
    assert "ПАМЯТЬ ПРОЕКТА" in res
    assert "Use per-task isolation" in res
    assert "PgBouncer" not in res
    assert "default_pool_size" not in res
    assert "Переходим к выполнению" not in res


@pytest.mark.asyncio
async def test_evidence_tool_goal_skips_crystals(monkeypatch):
    from app import ai_pipeline

    called = {"value": False}

    async def _boom():
        called["value"] = True
        raise AssertionError("DB should not be hit for evidence-tool crystal skip")

    monkeypatch.setenv("AI_PIPELINE_CRYSTALS_SKIP_OPERATIONAL", "true")
    monkeypatch.setattr("ai_core._get_db_pool", _boom)

    res = await ai_pipeline.load_memory_crystals(
        project_context="atra-web-ide",
        task_category="reasoning",
        user_prompt="Read file docs/curator_reports/standards/cursor_method.md. Quote line 3.",
    )
    assert res == ""
    assert called["value"] is False


def test_is_evidence_tool_goal_markers():
    from app import ai_pipeline

    assert ai_pipeline._is_evidence_tool_goal("git_diff src/agents/bridge/task_detector.py")
    assert ai_pipeline._is_evidence_tool_goal("printenv ATRA_ALLOW_GIT_MUTATE")
    assert not ai_pipeline._is_evidence_tool_goal("Сделай архитектурный анализ роя экспертов")
