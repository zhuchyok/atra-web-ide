"""Per-task isolation for overflow adopt, RAG namespace, and judge skip.

v150.70: overflow pool may execute a foreign expert's payload, but the worker
slot identity must not leak into the next task. RAG/judge read TaskContext
from contextvars instead of process-global expert_name.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, AsyncIterator, Iterable, Optional

logger = logging.getLogger("TaskIsolation")

_TASK_CTX: ContextVar[Optional["TaskContext"]] = ContextVar("atra_task_ctx", default=None)
_TASK_ID_RE = re.compile(r"\[task_id:([^\]]+)\]")


@dataclass(frozen=True)
class TaskContext:
    task_id: str
    expert_name: str
    source: str = ""
    domain_id: Optional[str] = None
    slot_expert_name: str = ""


def isolation_enabled() -> bool:
    return os.getenv("WORKER_TASK_ISOLATION", "true").lower() in ("true", "1", "yes")


def namespace_filter_enabled() -> bool:
    return os.getenv("RAG_NAMESPACE_FILTER", "true").lower() in ("true", "1", "yes")


def current_task_context() -> Optional[TaskContext]:
    return _TASK_CTX.get()


def push_task_context(
    task_id: str,
    expert_name: str,
    source: str = "",
    domain_id: Optional[str] = None,
    slot_expert_name: str = "",
) -> Token:
    ctx = TaskContext(
        task_id=str(task_id or ""),
        expert_name=str(expert_name or ""),
        source=str(source or ""),
        domain_id=str(domain_id) if domain_id else None,
        slot_expert_name=str(slot_expert_name or ""),
    )
    return _TASK_CTX.set(ctx)


def reset_task_context(token: Token) -> None:
    _TASK_CTX.reset(token)


@asynccontextmanager
async def bind_task_context(
    task_id: str,
    expert_name: str,
    source: str = "",
    domain_id: Optional[str] = None,
    slot_expert_name: str = "",
) -> AsyncIterator[TaskContext]:
    token = push_task_context(
        task_id=task_id,
        expert_name=expert_name,
        source=source,
        domain_id=domain_id,
        slot_expert_name=slot_expert_name,
    )
    try:
        ctx = current_task_context()
        assert ctx is not None
        yield ctx
    finally:
        reset_task_context(token)


def resolve_adopt_identity(
    slot_expert_name: str,
    payload_expert: Optional[str],
    pool_mode: bool,
) -> tuple[str, str, str]:
    """Return (run_expert, slot_expert, action) without mutating slot identity.

    action: own | adopt | skip
    """
    slot = (slot_expert_name or "").strip()
    payload = (payload_expert or "").strip()
    if not payload or payload == slot:
        return (payload or slot, slot, "own")
    if pool_mode:
        return (payload, slot, "adopt")
    return (slot, slot, "skip")


def extract_task_id(text: str) -> str:
    if not text:
        return ""
    match = _TASK_ID_RE.search(str(text))
    return match.group(1).strip() if match else ""


def judge_should_skip(
    question: str = "",
    answer: str = "",
    current_task_id: str = "",
    question_task_id: str = "",
    answer_task_id: str = "",
) -> bool:
    """Fail-open (skip scoring) when question/answer belong to different tasks."""
    qid = (question_task_id or extract_task_id(question) or "").strip()
    aid = (answer_task_id or extract_task_id(answer) or "").strip()
    if qid and aid and qid != aid:
        return True
    current = (current_task_id or "").strip()
    if not current:
        ctx = current_task_context()
        current = (ctx.task_id if ctx else "") or ""
    if current:
        if qid and qid != current:
            return True
        if aid and aid != current:
            return True
    return False


def _row_metadata(row: Any) -> dict:
    meta = None
    try:
        meta = row["metadata"] if not isinstance(row, dict) else row.get("metadata")
    except Exception:
        meta = getattr(row, "metadata", None)
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    return meta if isinstance(meta, dict) else {}


def filter_namespace_rows(
    rows: Iterable[Any],
    expert_name: Optional[str] = None,
) -> list:
    """Drop chunks owned by another expert. Generic docs (no expert_name) stay."""
    if not namespace_filter_enabled():
        return list(rows)
    current = (expert_name or "").strip()
    if not current:
        ctx = current_task_context()
        current = (ctx.expert_name if ctx else "") or ""
    if not current:
        return list(rows)
    kept = []
    dropped = 0
    for row in rows:
        owner = str(_row_metadata(row).get("expert_name") or "").strip()
        if owner and owner != current:
            dropped += 1
            continue
        kept.append(row)
    if dropped:
        logger.info(
            "[RAG-NS] dropped %s foreign chunk(s) for expert=%s kept=%s",
            dropped,
            current,
            len(kept),
        )
    return kept


def with_task_isolation(fn):
    """Bind TaskContext around process_task from payload fields."""

    @functools.wraps(fn)
    async def wrapper(task_data, *args, **kwargs):
        if not isolation_enabled() or not isinstance(task_data, dict):
            return await fn(task_data, *args, **kwargs)
        meta = task_data.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        token = push_task_context(
            task_id=str(task_data.get("task_id") or ""),
            expert_name=str(task_data.get("expert_name") or ""),
            source=str(meta.get("source") or ""),
            domain_id=str(meta["domain_id"]) if meta.get("domain_id") else None,
            slot_expert_name=str(
                task_data.get("_slot_expert_name") or os.getenv("EXPERT_NAME") or ""
            ),
        )
        try:
            return await fn(task_data, *args, **kwargs)
        finally:
            reset_task_context(token)

    return wrapper
