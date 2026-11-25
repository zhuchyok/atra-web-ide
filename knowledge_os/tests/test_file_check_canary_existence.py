"""BCANARY-prefixed existence asks must hit fast file-check (ДА/НЕТ + path)."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"


def _load_helpers():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    start = text.index("_FILE_CHECK_RE = re.compile(")
    end = text.index("\nasync def _try_direct_tool_reply")

    def extract_brain_canary_token(goal: str):
        m = re.search(r"BCANARY-[A-Za-z0-9_-]+", goal or "", re.I)
        return m.group(0) if m else None

    def is_brain_canary_probe(goal: str) -> bool:
        return extract_brain_canary_token(goal) is not None

    ns: dict = {
        "re": re,
        "os": os,
        "Any": Any,
        "Dict": Dict,
        "Optional": Optional,
        "extract_brain_canary_token": extract_brain_canary_token,
        "is_brain_canary_probe": is_brain_canary_probe,
    }
    exec(compile(text[start:end], str(VICTORIA_SERVER), "exec"), ns)
    return ns


def test_canary_prover_file_existence(tmp_path, monkeypatch):
    helpers = _load_helpers()
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    rel = "knowledge_os/app/expert_worker.py"
    (tmp_path / rel).parent.mkdir(parents=True)
    (tmp_path / rel).write_text("x=1\n", encoding="utf-8")

    goal = f"BCANARY-file01-deadbeef\nПроверь файл {rel}: существует ли? Ответ: ДА/НЕТ + путь."
    out = asyncio.run(helpers["_try_file_check_reply"](goal))
    assert out is not None
    assert out["knowledge"]["strategy"] == "fast_action_file_check"
    assert out["output"].startswith("ДА")
    assert rel in out["output"]


def test_canary_est_li_file(tmp_path, monkeypatch):
    helpers = _load_helpers()
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    rel = "knowledge_os/app/expert_stream_routing.py"
    (tmp_path / rel).parent.mkdir(parents=True)
    (tmp_path / rel).write_text("x=1\n", encoding="utf-8")
    goal = f"BCANARY-file02-x\nЕсть ли файл {rel}? Ответ: ДА/НЕТ + путь."
    out = asyncio.run(helpers["_try_file_check_reply"](goal))
    assert out and out["output"].startswith("ДА") and rel in out["output"]


def test_canary_presence_and_na_meste(tmp_path, monkeypatch):
    helpers = _load_helpers()
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    rel_a = "src/agents/bridge/victoria_server.py"
    rel_b = "configs/evals/consilium_v1.jsonl"
    for rel in (rel_a, rel_b):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("ok\n", encoding="utf-8")

    g1 = f"BCANARY-file03-x\nПроверь наличие {rel_a}. Ответ: ДА/НЕТ + путь."
    o1 = asyncio.run(helpers["_try_file_check_reply"](g1))
    assert o1 and o1["output"].startswith("ДА") and rel_a in o1["output"]

    g2 = f"BCANARY-file04-x\nФайл {rel_b} на месте? Ответ: ДА/НЕТ + путь."
    o2 = asyncio.run(helpers["_try_file_check_reply"](g2))
    assert o2 and o2["output"].startswith("ДА") and rel_b in o2["output"]
