import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.nightly_routing_quality_guard import GuardThresholds, evaluate_action


def test_guard_insufficient_events_goes_canary():
    th = GuardThresholds(min_events=20)
    d = evaluate_action(
        {
            "events_total_window": 5,
            "routing_win_rate": 1.0,
            "decision_regret_rate": 0.0,
            "latency_p95_ms": 10,
        },
        th,
    )
    assert d["action"] == "canary_only"
    assert "insufficient_events" in d["reason"]


def test_guard_hard_fail_goes_rollback():
    th = GuardThresholds(min_events=2)
    d = evaluate_action(
        {
            "events_total_window": 10,
            "routing_win_rate": 0.5,
            "decision_regret_rate": 0.4,
            "latency_p95_ms": 1000,
        },
        th,
    )
    assert d["action"] == "rollback"
    assert d["hard_fail"] is True


def test_guard_soft_fail_goes_canary():
    th = GuardThresholds(min_events=2, target_win_rate=0.95)
    d = evaluate_action(
        {
            "events_total_window": 10,
            "routing_win_rate": 0.92,
            "decision_regret_rate": 0.1,
            "latency_p95_ms": 100,
        },
        th,
    )
    assert d["action"] == "canary_only"
    assert d["hard_fail"] is False


def test_guard_green_goes_rollout():
    th = GuardThresholds(min_events=2, target_win_rate=0.8, target_regret_rate=0.2)
    d = evaluate_action(
        {
            "events_total_window": 10,
            "routing_win_rate": 0.9,
            "decision_regret_rate": 0.05,
            "latency_p95_ms": 120,
        },
        th,
    )
    assert d["action"] == "rollout"
