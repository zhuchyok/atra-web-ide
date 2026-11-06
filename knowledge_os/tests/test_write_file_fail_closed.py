"""v150.93: SystemTools.write_file fail-closed if SOURCE_GUARD cannot load."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_TOOLS = ROOT / "src" / "agents" / "tools" / "system_tools.py"


def _load_tools():
    spec = importlib.util.spec_from_file_location("system_tools_write_under_test", _TOOLS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _write_file_src() -> str:
    text = _TOOLS.read_text(encoding="utf-8")
    return text.split("async def write_file", 1)[1].split("async def run_ssh_command", 1)[0]


def test_write_file_source_returns_unavailable():
    fn = _write_file_src()
    assert "source_guard unavailable" in fn
    assert "if guard_file_write is None" in fn


@pytest.mark.asyncio
async def test_write_file_does_not_write_when_guard_unavailable(tmp_path, monkeypatch):
    mod = _load_tools()
    monkeypatch.setattr(
        mod.SystemTools, "_load_guard_file_write", staticmethod(lambda: None), raising=False
    )
    target = tmp_path / "probe.py"
    out = await mod.SystemTools.write_file(str(target), "print(1)\n")
    assert "SOURCE_GUARD" in out
    assert "unavailable" in out.lower()
    assert not target.exists()


@pytest.mark.asyncio
async def test_write_file_still_writes_when_guard_allows(tmp_path):
    mod = _load_tools()
    target = tmp_path / "ok_probe.py"
    out = await mod.SystemTools.write_file(str(target), "print(1)\n")
    assert out.startswith("OK:"), out
    assert target.read_text(encoding="utf-8") == "print(1)\n"


def _apply_patch_src() -> str:
    text = _TOOLS.read_text(encoding="utf-8")
    return text.split("async def apply_patch", 1)[1].split("class WebTools", 1)[0]


def test_apply_patch_source_returns_unavailable():
    fn = _apply_patch_src()
    assert "source_guard unavailable" in fn
    assert "_load_guard_file_write" in fn


@pytest.mark.asyncio
async def test_apply_patch_does_not_write_when_guard_unavailable(tmp_path, monkeypatch):
    mod = _load_tools()
    monkeypatch.setattr(
        mod.SystemTools, "_load_guard_file_write", staticmethod(lambda: None), raising=False
    )
    target = tmp_path / "probe.py"
    target.write_text("print(1)\n", encoding="utf-8")
    out = await mod.SystemTools.apply_patch(str(target), "print(1)", "print(2)")
    assert "SOURCE_GUARD" in out
    assert "unavailable" in out.lower()
    assert target.read_text(encoding="utf-8") == "print(1)\n"


@pytest.mark.asyncio
async def test_apply_patch_refuses_protected_agents_path(tmp_path):
    mod = _load_tools()
    target = tmp_path / "src" / "agents" / "core.py"
    target.parent.mkdir(parents=True)
    original = "def ping():\n    return 1\n"
    target.write_text(original, encoding="utf-8")
    out = await mod.SystemTools.apply_patch(str(target), "return 1", "return 2")
    assert "SOURCE_GUARD" in out
    assert "protected" in out.lower()
    assert target.read_text(encoding="utf-8") == original


@pytest.mark.asyncio
async def test_apply_patch_still_patches_when_guard_allows(tmp_path):
    mod = _load_tools()
    target = tmp_path / "ok_probe.py"
    target.write_text("print(1)\n", encoding="utf-8")
    out = await mod.SystemTools.apply_patch(str(target), "print(1)", "print(2)")
    assert "patched" in out.lower(), out
    assert target.read_text(encoding="utf-8") == "print(2)\n"
