"""p95 KISS: exclude probe/noise/resume from async TTC samples."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"


def _load_exclude_helpers():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    start = text.index("_DNA_EVAL_GOAL_MARKERS = (")
    end = text.index("\ndef _turn_log(")
    ns: dict = {"Optional": Optional}
    exec(compile(text[start:end], str(VICTORIA_SERVER), "exec"), ns)
    return ns["_exclude_from_async_ttc"], ns["_is_dna_eval_run"]


def test_exclude_cursor_pair_and_resume():
    exclude, _ = _load_exclude_helpers()
    assert exclude(source="cursor_pair", goal="проверь порты", handoff_reason="request_async_mode")
    assert exclude(source="", goal="user goal", handoff_reason="resumed_after_restart")
    assert exclude(source="probe", goal="x", handoff_reason="request_async_mode")


def test_exclude_keeps_normal_user_runs():
    exclude, _ = _load_exclude_helpers()
    assert not exclude(
        source="",
        goal="проанализируй очередь pending",
        handoff_reason="request_async_mode",
        strategy="deep_analysis",
        duration=42.0,
    )
    assert not exclude(
        source="telegram",
        goal="исправь баг в роутере",
        handoff_reason="early_async_analysis",
        duration=12.5,
    )


def test_exclude_fast_strategies_and_subsecond():
    exclude, _ = _load_exclude_helpers()
    assert exclude(
        source="",
        goal="что на 11434",
        handoff_reason="request_async_mode",
        strategy="fact_live_probe",
        duration=2.0,
    )
    assert exclude(
        source="",
        goal="проверь файл x.py",
        handoff_reason="early_async_analysis",
        strategy="fast_action_file_check",
        duration=1.0,
    )
    assert exclude(
        source="telegram",
        goal="толстая задача",
        handoff_reason="request_async_mode",
        duration=0.02,
    )


def test_exclude_still_covers_dna_eval():
    exclude, dna = _load_exclude_helpers()
    assert dna(source="dna_eval", goal="anything")
    assert exclude(source="dna_eval", goal="anything", handoff_reason="request_async_mode")


def test_record_async_ttc_uses_exclude_helper():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    rec = text[text.index("def _record_async_ttc(") : text.index("async def _push_ttc_sample(")]
    assert "_exclude_from_async_ttc(" in rec
    assert "handoff_reason=" in rec
    assert "strategy=" in rec
    assert "duration=" in rec
