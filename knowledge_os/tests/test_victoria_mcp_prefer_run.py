"""MCP victoria_chat must route heavy/curator/file goals to /run async."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MCP_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_mcp_server.py"
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"


def _load_prefer_run():
    """Extract _prefer_run_async without importing FastMCP."""
    text = MCP_SERVER.read_text(encoding="utf-8")
    start = text.index("def _prefer_run_async(")
    end = text.index("\ndef _parse_run_result(")
    ns: dict = {"os": os}
    exec(compile(text[start:end], str(MCP_SERVER), "exec"), ns)
    return ns["_prefer_run_async"]


def test_short_greeting_stays_on_chat():
    prefer_run = _load_prefer_run()
    assert prefer_run("привет") is False
    assert prefer_run("кто ты?") is False


def test_file_check_prefers_run():
    prefer_run = _load_prefer_run()
    goal = (
        "проверь файл /app/knowledge_os/app/expert_worker.py — есть ли там "
        "pip install в рантайме? Ответь: ОК или ПРОБЛЕМА + цитата"
    )
    assert prefer_run(goal) is True


def test_curator_fact_prefers_run():
    prefer_run = _load_prefer_run()
    assert prefer_run("CURATOR: health 8010 and models on 11434 — short facts only.") is True


def test_long_goal_prefers_run():
    prefer_run = _load_prefer_run()
    assert prefer_run("x" * 120) is True
    assert prefer_run("коротко") is False


def test_chat_routes_to_run_in_source():
    text = MCP_SERVER.read_text(encoding="utf-8")
    assert "_prefer_run_async(message)" in text
    assert "routing to /run async" in text
    assert "_run_async_and_poll" in text


def test_chat_file_check_ungated_in_server_source():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "_try_file_check_reply(goal)" in text
    idx = text.index("Live facts must ship on chat")
    window = text[idx : idx + 1800]
    assert "_try_file_check_reply(goal)" in window
    assert "[VICTORIA_FILE_CHECK] chat completions" in window
