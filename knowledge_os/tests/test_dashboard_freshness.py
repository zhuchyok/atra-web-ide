import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DASH = os.path.join(ROOT, "knowledge_os", "dashboard")
if DASH not in sys.path:
    sys.path.insert(0, DASH)


def test_rare_okrs_and_simulations_do_not_trip_stale_alert():
    from freshness import classify_source_freshness

    flag, stale = classify_source_freshness("okrs", 148233.0)
    assert stale is False
    assert "давно" in flag or "редко" in flag

    flag, stale = classify_source_freshness("simulations", 398626.0)
    assert stale is False


def test_operational_source_over_24h_is_stale_alert():
    from freshness import classify_source_freshness

    flag, stale = classify_source_freshness("tasks", 24 * 60 + 1)
    assert stale is True
    assert "устарело" in flag


def test_fresh_tasks_are_ok():
    from freshness import classify_source_freshness

    flag, stale = classify_source_freshness("knowledge_nodes", 1.2)
    assert stale is False
    assert "актуально" in flag


def test_empty_source_is_not_stale_alert():
    from freshness import classify_source_freshness

    flag, stale = classify_source_freshness("file_comments", None)
    assert stale is False
    assert "нет данных" in flag
