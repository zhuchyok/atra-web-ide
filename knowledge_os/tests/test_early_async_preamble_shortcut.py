"""p95 KISS: early_async / request_async skip strategy+understand LLM preamble."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"


def _load_early_async_shortcut():
    """Load shortcut + deps without importing victoria_server."""
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    # Helpers used by the shortcut (force-deep + analysis-heavy).
    force_start = text.index("def _force_deep_analysis_reason(")
    force_end = text.index("\ndef _has_no_clarification_instruction(")
    heavy_start = text.index("def _is_analysis_heavy_goal(")
    heavy_end = text.index("\ndef _early_async_preamble_shortcut(")
    short_start = heavy_end + 1  # starts at def _early_async...
    short_end = text.index("\ndef _is_planning_guidance_goal(")
    ns: dict = {
        "Optional": Optional,
        "Dict": Dict,
        "Any": Any,
    }
    exec(compile(text[force_start:force_end], str(VICTORIA_SERVER), "exec"), ns)
    exec(compile(text[heavy_start:heavy_end], str(VICTORIA_SERVER), "exec"), ns)
    exec(compile(text[short_start:short_end], str(VICTORIA_SERVER), "exec"), ns)
    return ns["_early_async_preamble_shortcut"]


def test_early_async_shortcut_returns_deep_analysis():
    fn = _load_early_async_shortcut()
    restated, strategy = fn("early_async_analysis", "проанализируй маршрутизацию подробно")
    assert restated == "проанализируй маршрутизацию подробно"
    assert strategy is not None
    assert strategy["strategy"] == "deep_analysis"
    assert strategy["reason"] == "early_async_analysis_skip_preamble"
    assert float(strategy["confidence"]) >= 0.9


def test_request_async_skips_preamble_for_analysis_heavy():
    fn = _load_early_async_shortcut()
    restated, strategy = fn("request_async_mode", "проанализируй маршрутизацию экспертов подробно")
    assert restated == "проанализируй маршрутизацию экспертов подробно"
    assert strategy is not None
    assert strategy["strategy"] == "deep_analysis"
    assert strategy["reason"] == "async_mode_skip_preamble"


def test_request_async_skips_preamble_for_force_deep():
    fn = _load_early_async_shortcut()
    restated, strategy = fn("request_async_mode", "объясни как работает Redis streams")
    assert restated.startswith("объясни")
    assert strategy is not None
    assert strategy["reason"] == "async_mode_skip_preamble"


def test_other_handoff_keeps_normal_preamble():
    fn = _load_early_async_shortcut()
    assert fn("timeout_enhanced_solve", "проанализируй что-то подробно") == (None, None)
    assert fn(None, "проанализируй что-то") == (None, None)
    assert fn("", "проанализируй что-то") == (None, None)


def test_request_async_short_non_deep_keeps_preamble():
    fn = _load_early_async_shortcut()
    # Too short / no analysis markers and no force-deep starter.
    assert fn("request_async_mode", "ok") == (None, None)


def test_handoff_wires_shortcut_into_background():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "_restated_goal, _strategy_result = _early_async_preamble_shortcut(reason, goal)" in text
    assert "restated_goal=_restated_goal" in text
    assert "strategy_result=_strategy_result" in text
