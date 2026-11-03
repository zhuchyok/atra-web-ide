"""Age helpers for blackboard goals. No Redis import — safe for unit tests."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

OPEN_GOAL_MAX_AGE_SEC = 86400


def goal_age_seconds(data: Dict[str, Any], now: Optional[datetime] = None) -> Optional[float]:
    raw = (data or {}).get("timestamp") or (data or {}).get("created_at")
    if raw is None:
        return None
    try:
        if isinstance(raw, (int, float)) or (
            isinstance(raw, str) and raw.replace(".", "", 1).isdigit()
        ):
            dt = datetime.fromtimestamp(float(raw), tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None
    current = now or datetime.now(timezone.utc)
    return max(0.0, (current - dt).total_seconds())


def is_fresh_open_goal(
    data: Dict[str, Any],
    max_age_sec: int = OPEN_GOAL_MAX_AGE_SEC,
    now: Optional[datetime] = None,
) -> bool:
    if (data or {}).get("status") not in ("unclaimed", "bidding_open"):
        return False
    age = goal_age_seconds(data, now=now)
    if age is None:
        return True
    return age <= max_age_sec
