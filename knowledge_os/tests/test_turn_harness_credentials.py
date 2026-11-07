import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "app" / "turn_harness" / "credentials.py"
_spec = importlib.util.spec_from_file_location("turn_harness_credentials", _PATH)
credentials = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(credentials)


def test_empty_is_absent(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "   ")
    assert credentials.resolve("TELEGRAM_BOT_TOKEN") is None
    info = credentials.describe("TELEGRAM_BOT_TOKEN")
    assert info["configured"] is False
    assert "value" not in info
    assert info["ref"] == "TELEGRAM_BOT_TOKEN"


def test_resolve_reads_current_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-a")
    assert credentials.resolve("TELEGRAM_BOT_TOKEN") == "secret-a"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-b")
    assert credentials.resolve("TELEGRAM_BOT_TOKEN") == "secret-b"
    info = credentials.describe("TELEGRAM_BOT_TOKEN")
    assert info == {"ref": "TELEGRAM_BOT_TOKEN", "configured": True, "source": "env"}
    assert "secret" not in str(info)
