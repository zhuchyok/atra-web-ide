"""p95 KISS: early_async_analysis skips strategy+understand LLM preamble."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"


def _load_early_async_shortcut():
    """Load only the shortcut helper without importing victoria_server."""
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    start = text.index("def _early_async_preamble_shortcut(")
    end = text.index("\ndef _is_planning_guidance_goal(")
    ns: dict = {
        "Optional": Optional,
        "Dict": Dict,
        "Any": Any,
    }
    exec(compile(text[start:end], str(VICTORIA_SERVER), "exec"), ns)
    return ns["_early_async_preamble_shortcut"]


def test_early_async_shortcut_returns_deep_analysis():
    fn = _load_early_async_shortcut()
    restated, strategy = fn("early_async_analysis", "проанализируй маршрутизацию подробно")
    assert restated == "проанализируй маршрутизацию подробно"
    assert strategy is not None
    assert strategy["strategy"] == "deep_analysis"
    assert strategy["reason"] == "early_async_analysis_skip_preamble"
    assert float(strategy["confidence"]) >= 0.9


def test_other_handoff_keeps_normal_preamble():
    fn = _load_early_async_shortcut()
    assert fn("timeout_enhanced_solve", "проанализируй что-то") == (None, None)
    assert fn(None, "проанализируй что-то") == (None, None)
    assert fn("", "проанализируй что-то") == (None, None)


def test_handoff_wires_shortcut_into_background():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "_restated_goal, _strategy_result = _early_async_preamble_shortcut(reason, goal)" in text
    assert "restated_goal=_restated_goal" in text
    assert "strategy_result=_strategy_result" in text
