"""File-check path parser must keep hyphens (…/atra-web-ide/…)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"
MCP_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_mcp_server.py"


def _load_file_check_re():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    start = text.index("_FILE_CHECK_RE = re.compile(")
    end = text.index("\n# Truncated per bible")
    ns: dict = {"re": re}
    exec(compile(text[start:end], str(VICTORIA_SERVER), "exec"), ns)
    return ns["_FILE_CHECK_RE"]


def test_hyphenated_host_path_preserved():
    rx = _load_file_check_re()
    goal = (
        "проверь файл /Users/bikos/Documents/atra-web-ide/knowledge_os/app/expert_worker.py "
        "— есть ли там pip install в рантайме?"
    )
    m = rx.match(goal[:120])
    assert m is not None
    path = m.group("path")
    assert "atra-web-ide" in path
    assert path.endswith("expert_worker.py")


def test_app_container_path_still_matches():
    rx = _load_file_check_re()
    goal = "проверь файл /app/knowledge_os/app/expert_worker.py — есть ли там pip install?"
    m = rx.match(goal[:120])
    assert m is not None
    assert m.group("path") == "/app/knowledge_os/app/expert_worker.py"


@pytest.mark.parametrize(
    "goal",
    [
        "существует ли файл /app/src/agents/bridge/victoria_server.py",
        "проверь существует ли файл /app/src/agents/bridge/victoria_server.py",
        "есть ли файл /app/src/agents/bridge/victoria_server.py",
        "проверь есть ли файл /app/src/agents/bridge/victoria_server.py?",
    ],
)
def test_existence_phrasing_matches_file_check_re(goal):
    rx = _load_file_check_re()
    m = rx.match(goal[:120])
    assert m is not None
    assert m.group("exists")
    assert m.group("path") == "/app/src/agents/bridge/victoria_server.py"


@pytest.mark.parametrize(
    "goal",
    [
        "существует ли файл в проекте",
        "есть ли файл с секретами",
        "проверь существует ли файл в репозитории",
        "аудит всех файлов проекта",
    ],
)
def test_existence_phrasing_rejects_project_wide_audits(goal):
    rx = _load_file_check_re()
    assert rx.match(goal[:120]) is None


def test_mcp_prefer_run_with_history_in_source():
    text = MCP_SERVER.read_text(encoding="utf-8")
    assert "prefer_run = _prefer_run_async(message)" in text
    assert "and not history" not in text.split("prefer_run = _prefer_run_async(message)")[1][:200]
    assert "Dialog context:" in text
    assert "min(VICTORIA_MCP_RUN_TIMEOUT_SEC, 120" not in text
    assert "is_fact_seeking_question" in text


def test_file_check_accepts_est_li_without_tam():
    """«есть ли X» without «там» must still scan."""
    import os
    from typing import Optional

    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    start = text.index("# Quoted membership needles:")
    end = text.index("\nasync def _try_file_check_reply")
    ns: dict = {"re": re, "os": os, "Optional": Optional}
    exec(compile(text[start:end], str(VICTORIA_SERVER), "exec"), ns)
    path = "/tmp/atra_file_check_phrase.py"
    Path(path).write_text("print('ok')\n", encoding="utf-8")
    try:
        out = ns["_file_check_scan"](path, " — есть ли pip install в рантайме?")
        assert out is not None
        assert out.startswith("ОК")
    finally:
        Path(path).unlink(missing_ok=True)
