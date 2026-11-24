"""Guards: /run/status must not stick on Redis inflight when work finished or timed out."""

from pathlib import Path

VICTORIA_SERVER = Path(__file__).resolve().parents[2] / "src/agents/bridge/victoria_server.py"


def test_sync_store_has_thin_redis_fallback():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    sync = text.split("async def _sync_store():", 1)[1].split('store["status"] = "processing"', 1)[
        0
    ]
    assert "thin fallback" in sync
    assert "full Redis sync failed" in sync
    assert "Redis sync failed task_id=" in sync


def test_get_run_status_prefers_local_terminal_over_redis_inflight():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    fn = text.split('@app.get("/run/status/{task_id}")', 1)[1].split(
        "async def _generate_via_mlx_or_ollama", 1
    )[0]
    assert "local_st in _terminal" in fn
    assert "redis_st in _inflight" in fn
    assert "status self-heal" in fn
    assert "VICTORIA_ASYNC_HARD_TIMEOUT_SEC" in fn
    assert "VICTORIA_ASYNC_INFLIGHT_STALE_SEC" in fn
    assert "updated_age=" in fn


def test_enhanced_solve_heartbeats_updated_at():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "async def _enhanced_solve_heartbeat()" in text
    assert "VICTORIA_ENHANCED_HEARTBEAT_SEC" in text
    # Heartbeat must wrap the wait on solve_task, not run after it.
    chunk = text.split("solve_task = asyncio.create_task(", 1)[1].split("if not done:", 1)[0]
    assert "_enhanced_solve_heartbeat" in chunk
    assert "asyncio.wait({solve_task}" in chunk
