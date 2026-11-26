"""Residual #65: file-check with «ttc» in path must not be fact_live_probe.

Goal like «проверь файл …/test_ttc_exclude_probe_noise.py — есть ли SyntaxError?»
contains substring «ttc» (FACT_SEEKING_MARKERS) and previously returned p50/p95.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"
TASK_DETECTOR = ROOT / "src" / "agents" / "bridge" / "task_detector.py"

TTC_FILE_CHECK_GOAL = (
    "проверь файл knowledge_os/tests/test_ttc_exclude_probe_noise.py — есть ли SyntaxError?"
)


def _load_file_check_re():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    start = text.index("_FILE_CHECK_RE = re.compile(")
    end = text.index("\n# Truncated per bible")
    ns: dict = {"re": re}
    exec(compile(text[start:end], str(VICTORIA_SERVER), "exec"), ns)
    return ns["_FILE_CHECK_RE"]


def test_ttc_path_goal_matches_file_check_re():
    rx = _load_file_check_re()
    m = rx.match(TTC_FILE_CHECK_GOAL[:120])
    assert m is not None
    assert "test_ttc_exclude_probe_noise.py" in m.group("path")


def test_ttc_path_would_false_positive_fact_seeking_markers():
    """Prove the hijack substrate: bare marker match on path substring."""
    text = TASK_DETECTOR.read_text(encoding="utf-8")
    assert '"ttc"' in text or "'ttc'" in text
    g = TTC_FILE_CHECK_GOAL.lower()
    assert "ttc" in g
    # Without file-check guard, format_live_fact_answer would emit metrics.
    assert any(x in g for x in ("ttc", "p95", "p50"))


def test_live_fact_builder_excludes_file_check_goals():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    fn = text.split("async def _build_live_fact_answer_for_run", 1)[1].split("async def ", 1)[0]
    assert "_FILE_CHECK_RE.match(_fc_prefix)" in fn
    assert "return None" in fn
    # Guard must appear before is_fact_seeking_question.
    assert fn.index("_FILE_CHECK_RE.match") < fn.index("is_fact_seeking_question")


def test_run_orders_file_check_before_live_fact():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    # /run: first file-check call must precede first live-fact builder after accept.
    run_idx = text.index("accept POST /run")
    run_window = text[run_idx : run_idx + 20000]
    assert "_try_file_check_reply(goal)" in run_window
    assert "_build_live_fact_answer_for_run(goal)" in run_window
    assert run_window.index("_try_file_check_reply(goal)") < run_window.index(
        "_build_live_fact_answer_for_run(goal)"
    )


def test_chat_orders_file_check_before_live_fact():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    chat_idx = text.index("Residual #65: FAST_ACTION file-check BEFORE live-fact")
    chat_window = text[chat_idx : chat_idx + 20000]
    assert "_try_file_check_reply(goal)" in chat_window
    assert "_build_live_fact_answer_for_run(goal)" in chat_window
    assert chat_window.index("_try_file_check_reply(goal)") < chat_window.index(
        "_build_live_fact_answer_for_run(goal)"
    )
