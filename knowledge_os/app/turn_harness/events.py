"""Журнал одного хода: append-only JSONL. Промпт — проекция, не второе хранилище."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

REASONS = frozenset(
    {
        "completed",
        "cancelled",
        "timeout",
        "max_steps",
        "tool_error",
        "approval_denied",
        "crashed",
    }
)


def _path(log_dir: str, task_id: str) -> str:
    safe = "".join(c for c in task_id if c.isalnum() or c in "-_")
    if not safe:
        raise ValueError("task_id empty")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, safe + ".jsonl")


def append_event(log_dir: str, task_id: str, event_type: str, **fields) -> dict:
    path = _path(log_dir, task_id)
    seq = 1
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    seq += 1
    event = {
        "seq": seq,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": event_type,
        **fields,
    }
    if event_type == "turn_closed" and event.get("reason") not in REASONS:
        raise ValueError(f"bad reason: {event.get('reason')}")
    line = json.dumps(event, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        if os.name != "nt":
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        fh.write(line)
        fh.flush()
    return event


def read_events(log_dir: str, task_id: str) -> list:
    path = _path(log_dir, task_id)
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def reason_for_store(store: dict) -> str:
    explicit = store.get("turn_end_reason")
    if explicit in REASONS:
        return explicit
    status = store.get("status")
    if status == "completed":
        return "completed"
    if status == "cancelled":
        return "cancelled"
    err = str(store.get("error") or "").lower()
    if "timeout" in err:
        return "timeout"
    if status == "failed":
        return "tool_error"
    return "crashed"


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n…[обрезано]"


def derive_prompt(events: list, *, max_chars: int = 12000, tool_max: int = 4000) -> str:
    anchors = []
    rest = []
    for ev in events:
        kind = ev.get("type")
        if kind == "turn_opened":
            anchors.append("goal: " + str(ev.get("goal") or ""))
        elif kind == "approval_decided":
            anchors.append("approval: " + str(ev.get("outcome") or ""))
        elif kind == "files_presented":
            anchors.append("presented: " + ",".join(ev.get("paths") or []))
        elif kind == "tool_result" and ev.get("status") == "error":
            anchors.append("tool_error: " + _clip(str(ev.get("text") or ""), tool_max))
        elif kind == "tool_result":
            rest.append("tool: " + _clip(str(ev.get("text") or ""), tool_max))
        elif kind == "model_message":
            rest.append("model: " + str(ev.get("text") or ""))
    head = "\n".join(anchors)
    if len(head) > max_chars:
        return head[:max_chars]
    budget = max_chars - len(head) - (1 if head else 0)
    tail = []
    used = 0
    for piece in reversed(rest):
        if used + len(piece) + 1 > budget:
            break
        tail.append(piece)
        used += len(piece) + 1
    body = "\n".join(reversed(tail))
    if head and body:
        return head + "\n" + body
    return head or body


def logging_enabled() -> bool:
    return os.getenv("TURN_LOG", "0").strip().lower() in {"1", "true", "yes", "on"}


def log_dir() -> str:
    return os.getenv("TURN_LOG_DIR", "logs/turns")


def sweep_open_turns(log_dir: str) -> int:
    if not os.path.isdir(log_dir):
        return 0
    closed = 0
    for name in os.listdir(log_dir):
        if not name.endswith(".jsonl"):
            continue
        task_id = name[: -len(".jsonl")]
        rows = read_events(log_dir, task_id)
        if rows and rows[-1].get("type") != "turn_closed":
            append_event(log_dir, task_id, "turn_closed", reason="crashed")
            closed += 1
    return closed
