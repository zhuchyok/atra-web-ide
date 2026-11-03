"""Classify Redis stream PEL entries: zombie / reclaim / keep.

XAUTOCLAIM is already called by expert_worker. This module decides which
pending rows may be claimed vs dropped. Live consumers (heartbeat) and
in-flight message ids stay in PEL until ACK after result.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Optional

DEFAULT_MIN_IDLE_MS = 300_000
DEFAULT_ZOMBIE_DELIVERIES = 10
DEFAULT_HEARTBEAT_TTL_SEC = 90


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def pending_id(entry: Mapping[str, Any]) -> str:
    return _as_text(entry.get("message_id") or entry.get("message-id") or "")


def _deliveries(entry: Mapping[str, Any]) -> int:
    try:
        return int(entry.get("times_delivered") or entry.get("times-delivered") or 0)
    except (TypeError, ValueError):
        return 0


def _idle_ms(entry: Mapping[str, Any]) -> int:
    try:
        return int(entry.get("time_since_delivered") or entry.get("time-since-delivered") or 0)
    except (TypeError, ValueError):
        return 0


def _consumer(entry: Mapping[str, Any]) -> str:
    return _as_text(entry.get("consumer"))


def live_consumers_from_hash(
    mapping: Optional[Mapping[Any, Any]],
    *,
    now: float,
    ttl_sec: int = DEFAULT_HEARTBEAT_TTL_SEC,
) -> set[str]:
    live: set[str] = set()
    if not mapping:
        return live
    ttl = max(1, int(ttl_sec))
    for raw in mapping.values():
        text = _as_text(raw).strip()
        if not text:
            continue
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        try:
            ts = float(obj.get("ts") or 0)
        except (TypeError, ValueError):
            continue
        if now - ts > ttl:
            continue
        name = _as_text(obj.get("consumer")).strip()
        if name:
            live.add(name)
    return live


def classify_pending(
    entries: Iterable[Mapping[str, Any]],
    *,
    live_consumers: Optional[set[str]] = None,
    inflight_ids: Optional[set[str]] = None,
    min_idle_ms: int = DEFAULT_MIN_IDLE_MS,
    zombie_deliveries: int = DEFAULT_ZOMBIE_DELIVERIES,
) -> dict[str, list[Mapping[str, Any]]]:
    live = live_consumers or set()
    inflight = inflight_ids or set()
    idle_cut = max(0, int(min_idle_ms))
    zombie_n = max(1, int(zombie_deliveries))
    zombies: list[Mapping[str, Any]] = []
    reclaim: list[Mapping[str, Any]] = []
    keep: list[Mapping[str, Any]] = []
    for entry in entries or []:
        msg_id = pending_id(entry)
        if msg_id and msg_id in inflight:
            keep.append(entry)
            continue
        if _deliveries(entry) > zombie_n:
            zombies.append(entry)
            continue
        if _idle_ms(entry) <= idle_cut:
            keep.append(entry)
            continue
        owner = _consumer(entry)
        if owner and owner in live:
            keep.append(entry)
            continue
        reclaim.append(entry)
    return {"zombies": zombies, "reclaim": reclaim, "keep": keep}
