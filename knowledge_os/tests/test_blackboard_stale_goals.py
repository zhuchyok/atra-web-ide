import os
import sys
from datetime import datetime, timedelta, timezone

APP_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from services.blackboard_freshness import is_fresh_open_goal


def test_fresh_bidding_open_stays():
    now = datetime.now(timezone.utc)
    goal = {
        "status": "bidding_open",
        "timestamp": (now - timedelta(minutes=20)).isoformat(),
    }
    assert is_fresh_open_goal(goal, max_age_sec=86400, now=now) is True


def test_week_old_bidding_open_is_stale():
    now = datetime.now(timezone.utc)
    goal = {
        "status": "bidding_open",
        "timestamp": (now - timedelta(days=8)).isoformat(),
    }
    assert is_fresh_open_goal(goal, max_age_sec=86400, now=now) is False


def test_claimed_never_treated_as_open():
    now = datetime.now(timezone.utc)
    goal = {
        "status": "claimed",
        "timestamp": now.isoformat(),
    }
    assert is_fresh_open_goal(goal, max_age_sec=86400, now=now) is False
