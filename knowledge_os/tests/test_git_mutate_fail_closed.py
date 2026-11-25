"""ATRA_ALLOW_GIT_MUTATE fail-closed (mirrors git_push gate)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_TOOLS = ROOT / "src" / "agents" / "tools" / "system_tools.py"


def _load_tools():
    spec = importlib.util.spec_from_file_location("git_tools_mutate_under_test", _TOOLS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.asyncio
async def test_git_add_refused_by_default(monkeypatch):
    mod = _load_tools()
    called = []

    def fake_run(args, timeout=20):
        called.append(list(args))
        return 0, "ok"

    monkeypatch.setattr(mod.GitTools, "_git_run", staticmethod(fake_run))
    monkeypatch.delenv("ATRA_ALLOW_GIT_MUTATE", raising=False)
    out = await mod.GitTools.git_add("README.md")
    assert "ATRA_ALLOW_GIT_MUTATE" in out
    assert called == []


@pytest.mark.asyncio
async def test_git_commit_runs_when_mutate_env(monkeypatch):
    mod = _load_tools()
    called = []

    def fake_run(args, timeout=20):
        called.append(list(args))
        return 0, "committed"

    monkeypatch.setattr(mod.GitTools, "_git_run", staticmethod(fake_run))
    monkeypatch.setenv("ATRA_ALLOW_GIT_MUTATE", "true")
    out = await mod.GitTools.git_commit("test msg")
    assert out.startswith("ok:")
    assert called and called[0][0] == "commit"


@pytest.mark.asyncio
async def test_git_push_still_needs_push_env_when_mutate_on(monkeypatch):
    mod = _load_tools()
    called = []

    def fake_run(args, timeout=20):
        called.append(list(args))
        return 0, "pushed"

    monkeypatch.setattr(mod.GitTools, "_git_run", staticmethod(fake_run))
    monkeypatch.setenv("ATRA_ALLOW_GIT_MUTATE", "true")
    monkeypatch.delenv("ATRA_ALLOW_GIT_PUSH", raising=False)
    out = await mod.GitTools.git_push("origin", "main")
    assert "ATRA_ALLOW_GIT_PUSH" in out
    assert called == []


@pytest.mark.asyncio
async def test_run_local_command_refuses_git_commit_shell(monkeypatch):
    mod = _load_tools()
    called = []

    def fake_run(*args, **kwargs):
        called.append(args)
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.delenv("ATRA_ALLOW_GIT_MUTATE", raising=False)
    monkeypatch.delenv("ATRA_ALLOW_GIT_PUSH", raising=False)
    out = await mod.SystemTools.run_local_command('git commit -m "x"')
    assert "ATRA_ALLOW_GIT_MUTATE" in out
    assert called == []
    out2 = await mod.SystemTools.run_local_command("git add -A && git status")
    assert "ATRA_ALLOW_GIT_MUTATE" in out2
    assert called == []


@pytest.mark.asyncio
async def test_run_local_command_allows_git_status_without_mutate(monkeypatch):
    mod = _load_tools()

    class _R:
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _R())
    monkeypatch.delenv("ATRA_ALLOW_GIT_MUTATE", raising=False)
    out = await mod.SystemTools.run_local_command("git status --short")
    assert "STDOUT: ok" in out
    out2 = await mod.SystemTools.run_local_command("git branch")
    assert "STDOUT: ok" in out2


@pytest.mark.asyncio
async def test_run_local_command_refuses_git_stash_and_py_wrapper(monkeypatch):
    mod = _load_tools()
    called = []

    def fake_run(*args, **kwargs):
        called.append(args)
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.delenv("ATRA_ALLOW_GIT_MUTATE", raising=False)
    assert "ATRA_ALLOW_GIT_MUTATE" in await mod.SystemTools.run_local_command("git stash")
    assert "ATRA_ALLOW_GIT_MUTATE" in await mod.SystemTools.run_local_command(
        "python -c \"import os; os.system('git add .')\""
    )
    assert called == []
