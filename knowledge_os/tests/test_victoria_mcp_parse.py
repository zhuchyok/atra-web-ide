import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.agents.bridge.victoria_mcp_parse import extract_text, format_run_result, is_victoria_stub


def test_extract_chat_completions():
    text, status = extract_text(
        {"choices": [{"message": {"content": "Я Виктория, Lead-разработчик ATRA."}}]}
    )
    assert status == "completed"
    assert "Виктория" in (text or "")


def test_extract_run_output():
    text, status = extract_text({"status": "completed", "output": "проверено: health ok"})
    assert status == "completed"
    assert "health ok" in (text or "")


def test_format_empty_with_task_id():
    msg = format_run_result({"status": "processing", "task_id": "abc-1"})
    assert "abc-1" in msg
    assert "victoria_task_status" in msg


def test_format_empty_without_task_id():
    msg = format_run_result({"status": "completed"})
    assert "пустой" in msg.lower()


def test_stub_rejected():
    assert is_victoria_stub("Task queued to PostgreSQL", status="processing")
    msg = format_run_result({"status": "processing", "output": "Task queued to PostgreSQL"})
    assert msg.startswith("❌")
