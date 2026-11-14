from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "knowledge_os" / "app" / "smart_worker_autonomous.py"


def test_validation_block_is_reachable_in_success_path():
    text = FILE.read_text(encoding="utf-8")
    fn = text.split("async def process_task(pool, task):", 1)[1].split(
        "async def worker_loop", 1
    )[0]
    success_idx = fn.find("if not is_error:")
    validation_idx = fn.find("validate_task_result", success_idx)
    completion_idx = fn.find("SET status = 'completed'", success_idx)
    assert success_idx != -1
    assert validation_idx != -1
    assert completion_idx != -1
    assert success_idx < validation_idx < completion_idx


def test_error_escalation_paths_not_marked_completed():
    text = FILE.read_text(encoding="utf-8")
    assert "Task {task_id} cancelled with board escalation" in text
    assert "SET status = 'cancelled', result = $2, updated_at = NOW()," in text
    assert "completed with board escalation after validation failure" not in text


def test_outer_exception_returns_before_post_finally_fallback():
    text = FILE.read_text(encoding="utf-8")
    fn = text.split("async def process_task(pool, task):", 1)[1].split(
        "async def worker_loop", 1
    )[0]
    except_chunk = fn.split("except Exception as e:", 1)[1].split("finally:", 1)[0]
    assert "\n        return\n" in except_chunk
