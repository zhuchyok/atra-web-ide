from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
APP_ROOT = os.path.join(ROOT, "knowledge_os", "app")
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

import nightly_learner as nl  # noqa: E402


def _reset_mode(monkeypatch, skip_above=500, force="auto", mode="normal"):
    monkeypatch.setattr(nl, "NIGHTLY_DISTILL_SKIP_ELIGIBLE_ABOVE", skip_above)
    monkeypatch.setattr(nl, "NIGHTLY_DISTILL_FORCE_MODE", force)
    monkeypatch.setattr(nl, "_DISTILL_MODE", mode)
    monkeypatch.setattr(nl, "_DISTILL_HIGH_STREAK", 0)
    monkeypatch.setattr(nl, "_DISTILL_LOW_STREAK", 0)


def test_huge_tail_is_idle_not_turbo(monkeypatch):
    _reset_mode(monkeypatch)
    mode, reason = nl._select_distill_mode(43903, 5)
    assert mode == "idle"
    assert reason == "tail_too_large_skip_drain"


def test_force_turbo_does_not_override_skip(monkeypatch):
    _reset_mode(monkeypatch, force="turbo")
    mode, reason = nl._select_distill_mode(43903, 5)
    assert mode == "idle"
    assert reason == "tail_too_large_skip_drain"


def test_modest_backlog_is_not_idle(monkeypatch):
    _reset_mode(monkeypatch)
    mode, _reason = nl._select_distill_mode(20, 5)
    assert mode != "idle"


@pytest.mark.asyncio
async def test_drain_skips_huge_tail_without_calling_distiller(monkeypatch):
    _reset_mode(monkeypatch)

    class FakeConn:
        async def close(self):
            pass

    async def fake_connect(_url):
        return FakeConn()

    called = []

    class FakeDistiller:
        async def distill_knowledge_batch(self):
            called.append(1)

    monkeypatch.setattr(nl.asyncpg, "connect", fake_connect)
    monkeypatch.setattr(nl, "get_distill_eligible_now", AsyncMock(return_value=43903))
    monkeypatch.setattr(nl, "_get_distiller_singleton", lambda: FakeDistiller())

    await nl.run_distillation_until_target()
    assert called == []


@pytest.mark.asyncio
async def test_continuous_distill_survives_closed_connection(monkeypatch):
    calls = {"n": 0}

    async def boom():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("distillation_db_connection_closed")

    async def fake_sleep(_sec):
        if calls["n"] >= 2:
            raise asyncio.CancelledError()

    monkeypatch.setattr(nl, "run_distillation_until_target", boom)
    monkeypatch.setattr(nl.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await nl.run_continuous_distillation()
    assert calls["n"] >= 2
