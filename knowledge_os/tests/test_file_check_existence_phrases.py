"""Existence phrasing («существует ли файл …») must hit fast_action_file_check."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"
EXISTING = "/app/src/agents/bridge/victoria_server.py"
MISSING = "/app/src/agents/bridge/definitely_missing_existence_probe.py"


def _load_try_file_check_reply():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    start = text.index("_FILE_CHECK_RE = re.compile(")
    end = text.index("\nasync def _try_direct_tool_reply")
    ns: dict = {
        "re": re,
        "os": os,
        "Any": Any,
        "Dict": Dict,
        "Optional": Optional,
    }
    exec(compile(text[start:end], str(VICTORIA_SERVER), "exec"), ns)
    return ns


def test_canonical_still_fast_file_check(tmp_path, monkeypatch):
    helpers = _load_try_file_check_reply()
    target = tmp_path / "victoria_server.py"
    target.write_text("print('ok')\n", encoding="utf-8")
    real_isfile = os.path.isfile
    real_exists = os.path.exists
    real_open = open

    def fake_exists(p):
        return p == EXISTING or real_exists(p)

    def fake_isfile(p):
        return p == EXISTING or real_isfile(p)

    def fake_open(file, *args, **kwargs):
        if str(file) == EXISTING:
            return real_open(target, *args, **kwargs)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(helpers["os"].path, "exists", fake_exists)
    monkeypatch.setattr(helpers["os"].path, "isfile", fake_isfile)
    monkeypatch.setattr("builtins.open", fake_open)

    goal = f"проверь файл {EXISTING} — есть ли там pip install в рантайме?"
    out = asyncio.run(helpers["_try_file_check_reply"](goal))
    assert out is not None
    assert out["knowledge"]["strategy"] == "fast_action_file_check"
    assert out["output"].startswith("ОК")


def test_exists_li_file_hits_fast_action(monkeypatch):
    helpers = _load_try_file_check_reply()
    host = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"
    assert host.is_file()

    def fake_isfile(p):
        return p == EXISTING

    monkeypatch.setattr(helpers["os"].path, "isfile", fake_isfile)
    monkeypatch.setattr(helpers["os"].path, "exists", fake_isfile)

    goal = f"существует ли файл {EXISTING}"
    out = asyncio.run(helpers["_try_file_check_reply"](goal))
    assert out is not None
    assert out["knowledge"]["strategy"] == "fast_action_file_check"
    assert out["output"].startswith("ФАЙЛ СУЩЕСТВУЕТ")
    assert EXISTING in out["output"]


def test_prover_exists_li_file_hits_fast_action(monkeypatch):
    helpers = _load_try_file_check_reply()

    def fake_isfile(p):
        return p == EXISTING

    monkeypatch.setattr(helpers["os"].path, "isfile", fake_isfile)
    monkeypatch.setattr(helpers["os"].path, "exists", fake_isfile)

    goal = f"проверь существует ли файл {EXISTING}"
    out = asyncio.run(helpers["_try_file_check_reply"](goal))
    assert out is not None
    assert out["knowledge"]["strategy"] == "fast_action_file_check"
    assert "СУЩЕСТВУЕТ" in out["output"]


def test_exists_li_missing_file_reports_not_found(monkeypatch):
    helpers = _load_try_file_check_reply()
    monkeypatch.setattr(helpers["os"].path, "isfile", lambda p: False)
    monkeypatch.setattr(helpers["os"].path, "exists", lambda p: False)

    goal = f"есть ли файл {MISSING}"
    out = asyncio.run(helpers["_try_file_check_reply"](goal))
    assert out is not None
    assert out["knowledge"]["strategy"] == "fast_action_file_check"
    assert out["output"] == f"ФАЙЛ НЕ НАЙДЕН: {MISSING}"


def test_project_wide_existence_does_not_fast_path():
    helpers = _load_try_file_check_reply()
    out = asyncio.run(helpers["_try_file_check_reply"]("существует ли файл в проекте"))
    assert out is None
