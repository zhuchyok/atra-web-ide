"""Regression: /run must honor async_mode passed in JSON body."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"


def test_task_request_supports_async_mode_field():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "class TaskRequest(BaseModel):" in text
    assert "async_mode: Optional[bool] = None" in text


def test_run_task_uses_body_async_mode_compatibility():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "if not async_mode and bool(getattr(body, \"async_mode\", False)):" in text
    assert "async_mode = True" in text
    assert "enabled from request body for compatibility" in text
