"""v138: Victoria stale-task DB cleanup must use asyncpg placeholders, not pending."""

from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "agents" / "bridge" / "victoria_server.py"


def _cleanup_sql_chunk() -> str:
    text = SRC.read_text(encoding="utf-8")
    start = text.index("async def _cleanup_stale_tasks")
    end = text.index("async def _load_tasks_from_db", start)
    return text[start:end]


def test_stale_cleanup_uses_asyncpg_interval_placeholder():
    chunk = _cleanup_sql_chunk()
    assert "INTERVAL '%s seconds'" not in chunk
    assert "make_interval(secs => $1::int)" in chunk
    assert "COALESCE(result, '') || $2" in chunk


def test_stale_cleanup_does_not_fail_pending_queue():
    chunk = _cleanup_sql_chunk()
    assert "WHERE status IN ('in_progress', 'processing', 'running')" in chunk
    assert "'pending'" not in chunk.split("WHERE status IN", 1)[1]
