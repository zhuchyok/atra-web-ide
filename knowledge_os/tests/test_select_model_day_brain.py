"""Day-better: _select_model_for_chat routes to qwen38/phi, not wisdom-24k."""

from __future__ import annotations

import importlib.util
from pathlib import Path

VS = Path(__file__).resolve().parents[2] / "src" / "agents" / "bridge" / "victoria_server.py"


def _load_select_fn(monkeypatch):
    """Exec only the selector helper with minimal stubs (avoid importing full server)."""
    text = VS.read_text(encoding="utf-8")
    start = text.index("def _select_model_for_chat")
    end = text.index("\n# Загружаем .env при старте", start)
    ns: dict = {"os": __import__("os"), "Optional": __import__("typing").Optional}
    exec(text[start:end], ns)  # noqa: S102
    return ns["_select_model_for_chat"]


def test_select_model_routes(monkeypatch):
    monkeypatch.setenv("VICTORIA_CHAT_SHORT_MODEL", "phi3.5:3.8b")
    monkeypatch.setenv("VICTORIA_MODEL", "victoria-qwen38:latest")
    fn = _load_select_fn(monkeypatch)
    assert fn("привет") == "phi3.5:3.8b"
    assert fn("как дела у команды атра сегодня вечером?") == "phi3.5:3.8b"
    assert "qwen38" in fn("Объясни коротко зачем Blackboard")
    assert "wisdom" not in fn("Объясни коротко зачем Blackboard")
    assert "qwen38" in fn("напиши python функцию сортировки")
    assert "qwen38" in fn("стратегия корпорации на год")
