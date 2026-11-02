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
    ]

    async def _fake_pool():
        return _FakePool(rows)

    monkeypatch.setenv("AI_PIPELINE_CRYSTALS_SKIP_OPERATIONAL", "true")
    monkeypatch.setenv("AI_PIPELINE_CRYSTALS_DENY_REGEX", r"pgbouncer|database port\s*:?\s*6432")
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
