"""Fail-closed: code/write goals must never return raw strategy-JSON (curator task_4 2026-11-16)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"

# Exact envelope from docs/curator_reports/artifacts_2026-11-16_12-00-19/task_4_*.json
TASK4_STRATEGY_ENVELOPE = (
    '{\n  "strategy": "quick_answer",\n  "reason": "Написание кода",\n'
    '  "confidence": 1.0,\n  "uncertainty_reason": "Это четкое задание с четкой целью"\n}'
)
TASK4_GOAL = "напиши одну строку кода на Python: вывод текущей даты"


def _load_strategy_envelope_helpers():
    """Load only the pure guard helpers without importing victoria_server."""
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    start = text.index("_STRATEGY_ENVELOPE_VALUES = frozenset(")
    end = text.index("\ndef _normalize_output_for_user(")
    ns: dict = {
        "json": json,
        "Any": Any,
        "Dict": Dict,
        "Optional": Optional,
    }
    exec(compile(text[start:end], str(VICTORIA_SERVER), "exec"), ns)
    return ns


@pytest.fixture(scope="module")
def helpers():
    return _load_strategy_envelope_helpers()


def test_task4_goal_is_code_write(helpers):
    assert helpers["_is_code_write_goal"](TASK4_GOAL) is True
    assert helpers["_is_code_write_goal"]("привет") is False
    assert helpers["_is_code_write_goal"]("что ты умеешь?") is False


def test_task4_output_looks_like_strategy_envelope(helpers):
    assert helpers["_looks_like_strategy_envelope"](TASK4_STRATEGY_ENVELOPE) is True
    assert helpers["_looks_like_strategy_envelope"](json.loads(TASK4_STRATEGY_ENVELOPE)) is True
    assert helpers["_looks_like_strategy_envelope"]("print(datetime.date.today())") is False
    assert (
        helpers["_looks_like_strategy_envelope"](
            '{"thought": "x", "tool": "finish", "tool_input": {"output": "hi"}}'
        )
        is False
    )


def test_code_goal_rejects_raw_strategy_envelope(helpers):
    out = helpers["_guard_code_goal_strategy_envelope"](TASK4_GOAL, TASK4_STRATEGY_ENVELOPE)
    assert "strategy" not in out or "quick_answer" not in out
    assert out.startswith("Ошибка:")
    assert "код" in out.lower() or "strategy-json" in out.lower()


def test_code_goal_unwraps_nested_code_field(helpers):
    payload = {
        "strategy": "quick_answer",
        "reason": "Написание кода",
        "confidence": 1.0,
        "code": "print(__import__('datetime').date.today())",
    }
    out = helpers["_guard_code_goal_strategy_envelope"](TASK4_GOAL, payload)
    assert out == "print(__import__('datetime').date.today())"
    assert not out.startswith("Ошибка:")


def test_non_code_goal_passes_through(helpers):
    out = helpers["_guard_code_goal_strategy_envelope"]("как дела?", TASK4_STRATEGY_ENVELOPE)
    assert "quick_answer" in out


def test_normalize_source_has_fail_closed_envelope_check():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "if _looks_like_strategy_envelope(raw):" in text
    assert "code_write_goal_override" in text
    assert "rejected_strategy_envelope" in text
    assert "_guard_code_goal_strategy_envelope" in text
