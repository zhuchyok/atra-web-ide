"""Разбор ответов Victoria для MCP: никогда не возвращать пустую строку."""

from __future__ import annotations

from typing import Any, Optional

STUB_MARKERS = (
    "queued to postgresql",
    "queued to postgres",
    "task queued",
    "status_url",
    "processing...",
    "все источники недоступны",
    "агенты временно недоступны",
    "rule-based статусный ответ",
    "rule-based research fallback",
    "[degraded_rule_fallback]",
    "ai временно недоступен",
    "fix not implemented",
)


def is_victoria_stub(text: str, status: Optional[str] = None) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    low = t.lower()
    if any(m in low for m in STUB_MARKERS):
        return True
    st = (status or "").strip().lower()
    if st in ("processing", "queued") and len(t) < 120 and "queued" in low:
        return True
    return False


def extract_text(result: dict[str, Any] | None) -> tuple[Optional[str], str]:
    """Достаёт текст ответа из /run, /run/status или chat completions."""
    if not isinstance(result, dict):
        return None, "unknown"
    status = str(result.get("status") or "completed")
    for key in ("output", "response", "result", "answer", "message", "content"):
        val = result.get(key)
        if isinstance(val, str) and val.strip():
            return val, status
        if isinstance(val, dict):
            nested = val.get("output") or val.get("content") or val.get("text")
            if isinstance(nested, str) and nested.strip():
                return nested, status
    choices = result.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        msg = first.get("message") if isinstance(first.get("message"), dict) else {}
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            return content, status
    return None, status


def format_run_result(result: dict[str, Any] | None) -> str:
    text, status = extract_text(result)
    if text is None:
        task_id = (result or {}).get("task_id") if isinstance(result, dict) else None
        if task_id:
            return (
                f"⏳ Victoria приняла задачу {task_id} (status={status}, тела ещё нет). "
                f"Забери через victoria_task_status."
            )
        return "❌ Victoria вернула пустой ответ (stub rejected)."
    if is_victoria_stub(text, status=status):
        return (
            "❌ Rejected Victoria stub/queue/rule-fallback response. "
            "Retry with sync /run or wait for a real expert answer — do not treat this as success."
        )
    return f"✅ {status}\n\n{text}"
