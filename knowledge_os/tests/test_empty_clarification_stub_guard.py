"""Guard: empty clarification_questions must not become a header-only chat stub.

Incident: docs/curator_reports/pair_2026-11-16_19-11-03.md
Victoria answered only «🤔 Мне нужно уточнить несколько деталей:» with no tools.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"
TASK_DETECTOR = ROOT / "src" / "agents" / "bridge" / "task_detector.py"

PAIR_GOAL = (
    "CURATOR CONTROL: Verify with facts only — (1) curl 8010/health "
    "(2) what models on 11434/11437/11436 via /api/ps names "
    "(3) is USER PROFILE inject wired in victoria_server (grep or import). "
    "Do not say ready without command evidence. List blockers if any."
)


def _load_helpers():
    import re

    td_ns: dict = {}
    exec(compile(TASK_DETECTOR.read_text(encoding="utf-8"), str(TASK_DETECTOR), "exec"), td_ns)

    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    # File-check constants used by clarify override.
    fc_start = text.index("_FILE_CHECK_RE = re.compile(")
    fc_end = text.index("\ndef _line_has_runtime_pip_install(")
    # #66: override calls _is_trivial_self_contained_code_goal (+ code-write markers).
    trivial_start = text.index("_CODE_WRITE_GOAL_MARKERS = (")
    trivial_end = text.index("\ndef _parse_json_object_loose(")
    start = text.index("def _override_need_clarification_strategy(")
    end = text.index("\ndef _has_explicit_tool_directive(")
    ns: dict = {
        "Any": Any,
        "Dict": Dict,
        "List": List,
        "Optional": Optional,
        "re": re,
        "json": __import__("json"),
        "is_introspection_goal": td_ns["is_introspection_goal"],
        "is_curator_standard_goal": td_ns["is_curator_standard_goal"],
        "is_fact_seeking_question": td_ns["is_fact_seeking_question"],
    }
    exec(compile(text[fc_start:fc_end], str(VICTORIA_SERVER), "exec"), ns)
    exec(compile(text[trivial_start:trivial_end], str(VICTORIA_SERVER), "exec"), ns)
    exec(compile(text[start:end], str(VICTORIA_SERVER), "exec"), ns)
    return ns


@pytest.fixture(scope="module")
def helpers():
    return _load_helpers()


def test_pair_goal_is_fact_seeking(helpers):
    assert helpers["is_fact_seeking_question"](PAIR_GOAL) is True


def test_pair_goal_overrides_need_clarification(helpers):
    out = helpers["_override_need_clarification_strategy"](
        PAIR_GOAL,
        {"strategy": "need_clarification", "reason": "ambiguous", "confidence": 0.7},
    )
    assert out["strategy"] == "deep_analysis"
    assert out["reason"] == "fact_seeking_no_clarify"


def test_empty_questions_filtered(helpers):
    assert helpers["_nonempty_clarification_questions"]([]) == []
    assert helpers["_nonempty_clarification_questions"](None) == []
    assert helpers["_nonempty_clarification_questions"](["", "  "]) == []
    assert helpers["_nonempty_clarification_questions"](["Какой порт?"]) == ["Какой порт?"]


def test_non_fact_goal_keeps_clarification(helpers):
    out = helpers["_override_need_clarification_strategy"](
        "сделай что-нибудь потом",
        {"strategy": "need_clarification", "reason": "ambiguous", "confidence": 0.6},
    )
    assert out["strategy"] == "need_clarification"


def test_file_check_goal_overrides_need_clarification(helpers):
    goal = (
        "проверь файл /app/knowledge_os/app/expert_worker.py — есть ли там "
        "pip install в рантайме? Ответь: ОК или ПРОБЛЕМА + цитата"
    )
    out = helpers["_override_need_clarification_strategy"](
        goal,
        {"strategy": "need_clarification", "reason": "ambiguous", "confidence": 0.7},
    )
    assert out["strategy"] == "deep_analysis"
    assert out["reason"] == "file_check_goal_no_clarify"


def test_operational_concrete_overrides_need_clarification(helpers):
    goal = "исправь IndentationError в src/agents/bridge/victoria_server.py"
    out = helpers["_override_need_clarification_strategy"](
        goal,
        {"strategy": "need_clarification", "reason": "ambiguous", "confidence": 0.6},
    )
    assert out["strategy"] == "deep_analysis"
    assert out["reason"] == "operational_concrete_no_clarify"
