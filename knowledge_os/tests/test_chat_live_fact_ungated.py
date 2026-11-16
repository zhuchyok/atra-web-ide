"""Chat live-fact must not require VICTORIA_DETERMINISTIC_CHAT.

Incident: curator sync chat returned 35s «отправьте через /run async» while
_build_live_fact_answer_for_run already had health/slots — gated by
deterministic_chat_enabled.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"
PAIR_SCRIPT = ROOT / "scripts" / "cursor_pair_victoria.py"


def test_chat_live_fact_not_gated_by_deterministic_flag():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "live_fact = await _build_live_fact_answer_for_run(goal)" in text
    # Must return live_fact without AND deterministic_chat_enabled
    idx = text.index("live_fact = await _build_live_fact_answer_for_run(goal)")
    window = text[idx : idx + 500]
    assert "if live_fact:" in window
    assert "deterministic_chat_enabled and live_fact" not in window


def test_chat_timeout_converts_to_async_handoff():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "converting to async handoff" in text
    assert "run_task(task_req, req, async_mode=True)" in text
    assert 'OPENAI_ASYNC_HANDOFF_WAIT_SEC", "90"' in text


def test_pair_script_prefers_run_async():
    text = PAIR_SCRIPT.read_text(encoding="utf-8")
    assert "run?async_mode=true" in text
    assert "def run_victoria_async" in text
    assert "prefer_async" in text
