from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from app.memory.journal_manager import record_worker_outcome

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "knowledge_os" / "app" / "expert_worker.py"


class _Acquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Acquire(self.conn)


def test_expert_worker_calls_journal_on_success_and_failure():
    text = WORKER.read_text(encoding="utf-8")
    assert "record_worker_outcome" in text
    assert text.count("record_worker_outcome") >= 2
    assert 'execution_mode="success"' in text
    assert 'execution_mode="failure"' in text


@pytest.mark.asyncio
async def test_record_worker_outcome_inserts(monkeypatch):
    expert_id = uuid.uuid4()
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=expert_id)
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    pool = _FakePool(conn)

    ok = await record_worker_outcome(
        pool,
        "Анна",
        uuid.uuid4(),
        summary="Task completed: audit queue",
        learnings="inflight=0",
        importance=6,
        execution_mode="success",
    )
    assert ok is True
    assert conn.fetchval.await_count == 1
    assert conn.execute.await_count == 1


@pytest.mark.asyncio
async def test_record_worker_outcome_skips_fast_path():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=uuid.uuid4())
    pool = _FakePool(conn)
    ok = await record_worker_outcome(
        pool,
        "Анна",
        uuid.uuid4(),
        summary="fast-path ping",
        execution_mode="fast_path",
    )
    assert ok is False
    assert conn.fetchval.await_count == 0


@pytest.mark.asyncio
async def test_record_worker_outcome_skips_missing_expert():
    ok = await record_worker_outcome(
        AsyncMock(),
        "",
        uuid.uuid4(),
        summary="Task completed: x",
    )
    assert ok is False
