"""Regression: sync /run should prefer safe mode by default."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"


def test_sync_safe_mode_default_is_enabled():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert 'VICTORIA_SYNC_SAFE_MODE = os.getenv("VICTORIA_SYNC_SAFE_MODE", "true")' in text


def test_sync_safe_mode_has_short_timeout_guard():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert 'VICTORIA_SYNC_SAFE_TIMEOUT_SEC = float(os.getenv("VICTORIA_SYNC_SAFE_TIMEOUT_SEC", "12"))' in text
    assert "timeout=VICTORIA_SYNC_SAFE_TIMEOUT_SEC" in text
    assert "VICTORIA_TIMEOUT_FALLBACK_TIMEOUT_SEC" in text
    assert "timeout=VICTORIA_TIMEOUT_FALLBACK_TIMEOUT_SEC" in text


def test_sync_safe_mode_failure_returns_timeout_fallback():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert 'logger.warning("[VICTORIA_CYCLE] sync safe mode failed: %s", safe_err)' in text
    assert 'return await _build_timeout_fallback_response("sync_safe_mode")' in text


def test_timeout_fallback_has_restated_goal_default_before_closure():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    restated_pos = text.index("restated_goal = None")
    fallback_def_pos = text.index("async def _build_timeout_fallback_response(")
    assert restated_pos < fallback_def_pos
