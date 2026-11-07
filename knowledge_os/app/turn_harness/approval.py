"""Один вопрос на одно действие. Пропуск только allowed-once."""

from __future__ import annotations

OUTCOMES = frozenset({"allowed-once", "rejected", "cancelled", "unavailable"})


async def decide(*, task_id, tool_name, call_id, reason, policy, answerer) -> str:
    if policy == "never":
        return "rejected"
    if policy != "ask":
        return "unavailable"
    if answerer is None:
        return "unavailable"
    try:
        raw = await answerer(
            {
                "task_id": task_id,
                "tool_name": tool_name,
                "call_id": call_id,
                "reason": reason,
            }
        )
    except Exception:
        return "unavailable"
    if raw in ("allowed-once", "rejected"):
        return raw
    return "unavailable"
