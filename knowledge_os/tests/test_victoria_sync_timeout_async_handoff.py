"""Regression: slow sync /run should hand off to async."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"


def test_timeout_paths_try_async_handoff_before_fallback():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert 'await _start_async_handoff("timeout_sync_safe_mode")' in text
    assert 'await _start_async_handoff("timeout_enhanced_solve")' in text
    assert 'await _start_async_handoff("timeout_agent_run")' in text
    assert 'return await _build_timeout_fallback_response("sync_safe_mode")' in text
    assert 'return await _build_timeout_fallback_response("enhanced.solve")' in text
    assert 'return await _build_timeout_fallback_response("agent.run")' in text


def test_async_response_exposes_handoff_reason():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert '"handoff_reason": reason' in text
    assert '"status_url": f"/run/status/{task_id}"' in text


def test_timeout_finally_clears_async_inflight():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "async def _clear_async_inflight(task_id: str)" in text
    assert "await _clear_async_inflight(task_id)" in text
    assert text.count("await _clear_async_inflight(task_id)") >= 2


def test_startup_fails_orphaned_inflight():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "async def _fail_orphaned_inflight_on_startup()" in text
    assert "_create_tracked_task(_fail_orphaned_inflight_on_startup())" in text
    assert "orphaned after Victoria restart" in text


def test_watchdog_extends_for_enhanced_solve_not_label():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "watchdog extend" in text
    assert "no deep progress" in text
    assert '"enhanced_solve"' in text
