from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_CORE = ROOT / "knowledge_os" / "app" / "ai_core.py"


def test_canary_daemon_does_not_create_coroutine_without_running_loop():
    text = AI_CORE.read_text(encoding="utf-8")
    assert "asyncio.create_task(_canary_daemon_loop())" not in text
    assert "_loop = asyncio.get_running_loop()" in text
    assert "_loop.create_task(_canary_daemon_loop())" in text
    assert "_atra_canary_daemon_started" in text
    assert "Already running for this event loop" in text
    assert "Deferred start: no running loop at import time" in text
