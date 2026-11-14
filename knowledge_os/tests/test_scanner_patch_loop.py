"""v152: scanner patch loop — classify → write → compile PASS → git_push deny.

No LLM. Mini-swe contract: evidence is command/output/PASS, not «готово».
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_SCANNER = ROOT / "knowledge_os" / "app" / "medic" / "log_scanner.py"
_TOOLS = ROOT / "src" / "agents" / "tools" / "system_tools.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_scanner = _load(_SCANNER, "scanner_patch_loop_under_test")


def _load_tools():
    return _load(_TOOLS, "tools_patch_loop_under_test")


def test_unprotected_typeerror_is_patch_and_may_write():
    msg = (
        'File "/workspace/atra-web-ide/src/auto_guard_probe.py", line 4, in add\n'
        "TypeError: unsupported operand"
    )
    klass = _scanner.classify_scanner_incident(
        "dynamic-1", {"type": "TypeError", "message": msg}
    )
    assert klass == "patch"
    tools = _scanner.blocked_tools_for_scanner_class(klass)
    assert "write_file" not in tools
    assert "apply_patch" not in tools
    assert "run_terminal_cmd" not in tools
    assert "git_push" in tools
    goal = _scanner.build_scanner_goal("dynamic-1", {"type": "TypeError", "message": msg}, klass, "src/auto_guard_probe.py")
    assert "command" in goal and "PASS" in goal
    assert "git_push" in goal


def test_core_typeerror_is_human_and_cannot_write_or_shell():
    msg = (
        'File "/workspace/atra-web-ide/src/agents/bridge/victoria_server.py", line 10\n'
        "TypeError: boom"
    )
    klass = _scanner.classify_scanner_incident(
        "victoria-agent", {"type": "TypeError", "message": msg}
    )
    assert klass == "human"
    tools = _scanner.blocked_tools_for_scanner_class(klass)
    assert "write_file" in tools
    assert "run_terminal_cmd" in tools
    assert "ssh_run" in tools
    assert "git_push" in tools


@pytest.mark.asyncio
async def test_patch_write_compiles_and_cannot_push(tmp_path, monkeypatch):
    tools = _load_tools()
    monkeypatch.delenv("ATRA_ALLOW_GIT_PUSH", raising=False)
    target = tmp_path / "auto_guard_probe.py"
    broken = "def add(a, b):\n    return a + None\n"
    target.write_text(broken, encoding="utf-8")
    broken_ns: dict = {}
    exec(broken, broken_ns)
    with pytest.raises(TypeError):
        broken_ns["add"](1, 2)

    fixed = "def add(a, b):\n    return a + b\n"
    out = await tools.SystemTools.write_file(str(target), fixed)
    assert out.startswith("OK:"), out
    assert target.read_text(encoding="utf-8") == fixed
    fixed_ns: dict = {}
    exec(fixed, fixed_ns)
    assert fixed_ns["add"](1, 2) == 3

    called = []

    def fake_run(*args, **kwargs):
        called.append(args)
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr(tools.subprocess, "run", fake_run)
    denied = await tools.SystemTools.run_local_command("git push origin main")
    assert "ATRA_ALLOW_GIT_PUSH" in denied
    assert called == []
    node = await tools.SystemTools.run_local_command(
        "node -e \"require('child_process').execSync('git push')\""
    )
    assert "ATRA_ALLOW_GIT_PUSH" in node
    assert called == []


@pytest.mark.asyncio
async def test_patch_cannot_write_protected_core(tmp_path):
    tools = _load_tools()
    target = tmp_path / "src" / "agents" / "bridge" / "victoria_server.py"
    target.parent.mkdir(parents=True)
    original = "def ping():\n    return 1\n"
    target.write_text(original, encoding="utf-8")
    out = await tools.SystemTools.write_file(str(target), "def ping():\n    return 2\n")
    assert "SOURCE_GUARD" in out
    assert "protected" in out.lower()
    assert target.read_text(encoding="utf-8") == original
