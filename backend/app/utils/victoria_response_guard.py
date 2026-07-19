"""
Guard against treating Victoria queue/ack stubs as real answers.
(Mirror of knowledge_os/app/victoria_response_guard.py — keep in sync.)
"""

from __future__ import annotations

import re
from typing import Any, Optional

_STUB_MARKERS = (
    "queued to postgresql",
    "queued to postgres",
    "task queued",
    "status_url",
    'strategy": "queued',
    "strategy': 'queued",
    "processing...",
    "требуется больше времени для анализа",
    "отправьте запрос через /run с async_mode=true",
    "все источники недоступны",
    "агенты временно недоступны",
    "rule-based статусный ответ",
    "rule-based research fallback",
    "[degraded_rule_fallback]",
    "llm временно недоступен",
    "ai временно недоступен",
    "fix not implemented",
    "[incomplete]",
    "текст ответа не был сохранён",
    "задача выполняется дольше обычного",
    "empty_result",
)


def is_victoria_stub(text: Optional[str], *, status: Optional[str] = None) -> bool:
    st = (status or "").strip().lower()
    t = (text or "").strip()
    if not t:
        return True
    low = t.lower()
    if any(m in low for m in _STUB_MARKERS):
        return True
    if re.search(r"⏳\s*task\s+[0-9a-f-]{36}\s+queued", low):
        return True
    if st in ("processing", "queued") and len(t) < 120 and "queued" in low:
        return True
    return False


def extract_victoria_text(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload.strip()
    if not isinstance(payload, dict):
        return str(payload).strip()
    for key in ("output", "result", "response", "directive_text"):
        val = payload.get(key)
        if val:
            return str(val).strip()
    return ""


def victoria_status(payload: Any) -> str:
    if isinstance(payload, dict):
        return str(payload.get("status") or "").strip().lower()
    return ""


def reject_if_stub(payload: Any) -> Optional[str]:
    text = extract_victoria_text(payload)
    status = victoria_status(payload)
    if is_victoria_stub(text, status=status):
        return f"victoria_stub:{status or 'unknown'}"
    return None
