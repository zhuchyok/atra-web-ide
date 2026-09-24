"""Regression: startup warmup must include strategist/executor model envs."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"


def test_warmup_includes_executor_and_strategist_models():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    start = text.index("async def warmup_victoria():")
    chunk = text[start : start + 1000]
    assert 'os.getenv("VICTORIA_PLANNER_MODEL", "").strip()' in chunk
    assert 'os.getenv("VICTORIA_MODEL", "").strip()' in chunk
    assert 'os.getenv("VICTORIA_STRATEGIST_MODEL", "").strip()' in chunk
    assert 'os.getenv("VICTORIA_EXECUTOR_MODEL", "").strip()' in chunk


def test_warmup_has_lock_and_busy_retries():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    start = text.index("async def warmup_victoria():")
    chunk = text[start : start + 6000]
    assert "VICTORIA_WARMUP_LOCK_PATH" in chunk
    assert "Warmup already running in another worker" in chunk
    assert "VICTORIA_WARMUP_RETRY_COUNT" in chunk
    assert "is_busy" in chunk
    assert "_deferred_warmup_retry(" in text
    assert "VICTORIA_WARMUP_DEFER_BUSY_RETRY" in text
    assert "/api/ps" in text
    assert "VICTORIA_WARMUP_KEEP_ALIVE_SEC" in text
    assert "VICTORIA_WARMUP_MIN_INTERVAL_SEC" in text
    assert "Warmup cooldown active" in text
