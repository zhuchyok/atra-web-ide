"""
Per-expert Redis Stream routing for expert workers.

World practice: partition queues by consumer key (Kafka keyed topics, SQS per-worker
queues) instead of one shared fan-out stream with application-level filtering.

Rollback: EXPERT_STREAM_DEDICATED=false restores legacy shared stream ``expert_tasks``.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

SHARED_EXPERT_STREAM = "expert_tasks"
OVERFLOW_EXPERT_STREAM = "expert_tasks:overflow"
EXPERT_WORKERS_GROUP = "expert_workers"


def is_dedicated_routing_enabled() -> bool:
    return os.getenv("EXPERT_STREAM_DEDICATED", "true").lower() in ("true", "1", "yes")


def normalize_expert_name(expert_name: Optional[str]) -> str:
    return (expert_name or "").strip()


def dedicated_stream_for_expert(expert_name: Optional[str]) -> str:
    expert = normalize_expert_name(expert_name) or "unknown"
    return f"{SHARED_EXPERT_STREAM}:{expert}"


def dispatch_stream_for_expert(expert_name: Optional[str]) -> str:
    if is_dedicated_routing_enabled() and normalize_expert_name(expert_name):
        return dedicated_stream_for_expert(expert_name)
    return SHARED_EXPERT_STREAM


def is_overflow_expert(expert_name: Optional[str]) -> bool:
    """Check if this is an overflow/fallback expert name (Инна, Юлия, etc)."""
    name = normalize_expert_name(expert_name).lower()
    # Over:low/fallback experts listen on overflow stream
    overflow_names = {normalize_expert_name(n).lower() for n in
                     os.getenv("EXPERT_OVERFLOW_NAMES", "Инна,Юлия").split(",")}
    return name in overflow_names


def resolve_push_stream(stream_name: str, data: Dict[str, Any]) -> str:
    """Route push_to_stream to dedicated stream when expert_name is known."""
    if not is_dedicated_routing_enabled():
        return stream_name
    expert = normalize_expert_name(data.get("expert_name"))
    if expert:
        # If the expert is an overflow recipient, push to overflow stream
        if is_overflow_expert(expert):
            return OVERFLOW_EXPERT_STREAM
        return dispatch_stream_for_expert(expert)
    if stream_name == SHARED_EXPERT_STREAM:
        return stream_name
    return stream_name


def redis_stream_key(stream_name: str) -> str:
    return f"stream:{stream_name}"


def worker_stream_name(expert_name: Optional[str]) -> str:
    if is_overflow_expert(expert_name):
        return OVERFLOW_EXPERT_STREAM
    if is_dedicated_routing_enabled() and normalize_expert_name(expert_name):
        return dedicated_stream_for_expert(expert_name)
    return SHARED_EXPERT_STREAM


async def ensure_consumer_group(client, stream_name: str, group: str = EXPERT_WORKERS_GROUP) -> None:
    try:
        await client.xgroup_create(redis_stream_key(stream_name), group, mkstream=True)
    except Exception:
        pass


async def publish_expert_payload(
    client,
    expert_name: Optional[str],
    payload: Dict[str, Any],
    *,
    maxlen: int = 10000,
) -> Optional[str]:
    stream = dispatch_stream_for_expert(expert_name or payload.get("expert_name"))
    await ensure_consumer_group(client, stream)
    return await client.xadd(
        redis_stream_key(stream),
        {"payload": json.dumps(payload, ensure_ascii=False)},
        maxlen=maxlen,
    )
