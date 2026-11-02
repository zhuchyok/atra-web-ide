"""Overflow process_task must stamp last_real_progress_at (hung detector column)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "knowledge_os" / "app" / "expert_worker.py"


def test_mark_llm_call_stamps_last_real_progress_at():
    text = WORKER.read_text(encoding="utf-8")
    start = text.index("async def _mark_llm_call")
    chunk = text[start : start + 900]
    assert "last_llm_call_at = NOW()" in chunk
    assert "last_real_progress_at = NOW()" in chunk
    assert "status = 'in_progress'" in chunk


def test_in_progress_pickup_stamps_last_real_progress_at():
    text = WORKER.read_text(encoding="utf-8")
    start = text.index("UPDATE tasks SET status = 'in_progress'")
    chunk = text[start : start + 200]
    assert "last_real_progress_at = NOW()" in chunk
    assert "updated_at = NOW()" in chunk
