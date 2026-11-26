"""MCP victoria_execute_plan: ready plan skips /orchestrate (Wave2 hands path)."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[2]
MOD = ROOT / "src" / "agents" / "bridge" / "victoria_mcp_server.py"


def _load():
    import sys

    bridge = str(ROOT / "src" / "agents" / "bridge")
    if bridge not in sys.path:
        sys.path.insert(0, bridge)
    # Prefer package import used in production.
    src_root = str(ROOT / "src")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    if src_root not in sys.path:
        sys.path.insert(0, src_root)
    spec = importlib.util.spec_from_file_location("victoria_mcp_server_under_test", MOD)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_coerce_execution_plan_json():
    m = _load()
    assert m.coerce_execution_plan_json(None) is None
    assert m.coerce_execution_plan_json("  ") is None
    plan = m.coerce_execution_plan_json(json.dumps([{"action": "read_file", "path": "a.txt"}]))
    assert isinstance(plan, list) and plan[0]["action"] == "read_file"
    # Cursor MCP may pass an already-decoded list
    plan2 = m.coerce_execution_plan_json([{"action": "read_file", "path": "b.txt"}])
    assert plan2[0]["path"] == "b.txt"
    try:
        m.coerce_execution_plan_json("{}")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_ready_plan_skips_orchestrate(tmp_path: Path):
    m = _load()
    f = tmp_path / "hello.txt"
    f.write_text("ready-plan-ok", encoding="utf-8")
    plan_json = json.dumps([{"action": "read_file", "path": "hello.txt"}])

    with patch.object(m.httpx, "AsyncClient") as client_cls:
        client_cls.return_value.__aenter__ = AsyncMock(
            side_effect=AssertionError("orchestrate must be skipped")
        )
        out = asyncio.run(
            m.victoria_execute_plan(
                goal="ignore-llm",
                workspace_path=str(tmp_path),
                approve_writes=False,
                execution_plan_json=plan_json,
            )
        )

    assert "ready-plan-ok" in out
    assert "/orchestrate skipped" in out
    assert "⏱️" not in out
