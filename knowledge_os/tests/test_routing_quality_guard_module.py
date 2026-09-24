import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.routing_quality_guard import GuardThresholds, evaluate_guard_action, run_routing_quality_guard_once


class _FakeRedis:
    def __init__(self, rows):
        self.rows = rows
        self.kv = {}

    async def xrevrange(self, _stream, count=100):
        return self.rows[:count]

    async def set(self, k, v):
        self.kv[k] = v


@pytest.mark.asyncio
async def test_guard_once_apply_sets_flags():
    row = (
        "1789244632662-0",
        {
            "ts": "1789244632658",
            "selected_route": "ollama_studio",
            "selected_model": "victoria-wisdom-24k:latest",
            "latency_ms": "7.7",
            "success": "1",
            "reason": "ok",
        },
    )
    r = _FakeRedis([row, row, row])
    rep = await run_routing_quality_guard_once(
        r,
        window_hours=24,
        count=100,
        apply_action=True,
        thresholds=GuardThresholds(min_events=2, target_win_rate=0.8, target_regret_rate=0.2),
    )
    assert rep["decision"]["action"] == "rollout"
    assert r.kv["system:contract_enforce"] == "1"
    assert r.kv["system:routing_guard:last_action"] == "rollout"


def test_evaluate_guard_action_hard_fail():
    d = evaluate_guard_action(
        {
            "events_total_window": 50,
            "routing_win_rate": 0.6,
            "decision_regret_rate": 0.3,
            "latency_p95_ms": 1000,
        },
        GuardThresholds(min_events=10),
    )
    assert d["action"] == "rollback"
