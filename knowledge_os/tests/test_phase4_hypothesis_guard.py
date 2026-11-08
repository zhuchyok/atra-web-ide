from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
APP_ROOT = os.path.join(ROOT, "knowledge_os", "app")
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from app import orchestrator_phases as phases


class _FakeConn:
    def __init__(self, nodes):
        self.nodes = nodes
        self.inserted = []
        self.executed = []

    async def fetch(self, query, *args):
        return self.nodes

    async def fetchrow(self, query, *args):
        return {"content": "other", "domain": "other-domain"}

    async def fetchval(self, query, *args):
        self.inserted.append(args)
        return "new-kn"

    async def execute(self, query, *args):
        self.executed.append(args)


def test_loop_breaker_text_is_not_persistable():
    assert phases.is_persistable_hypothesis(None) is False
    assert phases.is_persistable_hypothesis("") is False
    assert (
        phases.is_persistable_hypothesis(
            "[LOOP-BREAKER] превышен лимит повторов пайплайна для этого запроса"
        )
        is False
    )
    assert phases.is_persistable_hypothesis("петля сломана") is False
    assert phases.is_persistable_hypothesis("Связь доменов: X влияет на Y") is True


@pytest.mark.asyncio
async def test_phase4_skips_llm_when_debates_disabled(monkeypatch):
    monkeypatch.setenv("HYPOTHESIS_DEBATES_ENABLED", "false")
    called = []

    async def run_cursor(prompt):
        called.append(prompt)
        return "Связь доменов: X влияет на Y"

    conn = _FakeConn(
        [{"id": "n1", "content": "fact a", "domain": "A", "metadata": {}, "domain_id": 1}]
    )

    async def no_backlog(_conn):
        return False

    result = await phases.phase_4_cross_domain(
        conn,
        None,
        run_cursor_agent=run_cursor,
        heavy_phase_step_timeout_sec=5,
        execution_focus=False,
        has_execution_backlog=no_backlog,
    )

    assert called == []
    assert conn.inserted == []
    assert conn.executed == [("n1",)]
    assert result["skipped"] == "debates_disabled"


@pytest.mark.asyncio
async def test_phase4_does_not_insert_loop_breaker_when_debates_on(monkeypatch):
    monkeypatch.setenv("HYPOTHESIS_DEBATES_ENABLED", "true")

    async def run_cursor(_prompt):
        return "[LOOP-BREAKER] превышен лимит повторов пайплайна для этого запроса"

    conn = _FakeConn(
        [{"id": "n1", "content": "fact a", "domain": "A", "metadata": {}, "domain_id": 1}]
    )

    async def no_backlog(_conn):
        return False

    await phases.phase_4_cross_domain(
        conn,
        None,
        run_cursor_agent=run_cursor,
        heavy_phase_step_timeout_sec=5,
        execution_focus=False,
        has_execution_backlog=no_backlog,
    )

    assert conn.inserted == []
    assert conn.executed == [("n1",)]
