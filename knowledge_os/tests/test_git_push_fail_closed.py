"""v150.95: GitTools.git_push fail-closed unless ATRA_ALLOW_GIT_PUSH."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_TOOLS = ROOT / "src" / "agents" / "tools" / "system_tools.py"


def _load_tools():
    spec = importlib.util.spec_from_file_location("git_tools_push_under_test", _TOOLS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_git_push_source_requires_allow_env():
    text = _TOOLS.read_text(encoding="utf-8")
    fn = text.split("async def git_push", 1)[1].split("async def git_pr_create", 1)[0]
    assert "ATRA_ALLOW_GIT_PUSH" in fn


@pytest.mark.asyncio
async def test_git_push_refused_by_default(monkeypatch):
    mod = _load_tools()
    called = []

    def fake_run(args, timeout=20):
        called.append(list(args))
        return 0, "pushed"

    monkeypatch.setattr(mod.GitTools, "_git_run", staticmethod(fake_run))
    monkeypatch.delenv("ATRA_ALLOW_GIT_PUSH", raising=False)
    out = await mod.GitTools.git_push("origin", "main")
    assert "ATRA_ALLOW_GIT_PUSH" in out
    assert "rejected" in out.lower()
    assert called == []


@pytest.mark.asyncio
async def test_git_push_runs_when_allow_env(monkeypatch):
    mod = _load_tools()
    called = []

    def fake_run(args, timeout=20):
        called.append(list(args))
        return 0, "pushed"

    monkeypatch.setattr(mod.GitTools, "_git_run", staticmethod(fake_run))
    monkeypatch.setenv("ATRA_ALLOW_GIT_PUSH", "true")
    out = await mod.GitTools.git_push("origin", "main")
    assert out.startswith("ok:")
    assert called == [["push", "--no-verify", "origin", "main"]]


def test_git_push_not_in_allowed_tools():
    text = (ROOT / "src" / "agents" / "core" / "executor.py").read_text(encoding="utf-8")
    start = text.split("ALLOWED_TOOLS = {", 1)[1].split("}", 1)[0]
    assert '"git_push"' not in start
    prompt = text.split("СПИСОК ДОПУСТИМЫХ TOOL:", 1)[1].split("\n", 1)[0]
    assert "git_push" not in prompt


def test_run_local_command_source_blocks_git_push():
    fn = _TOOLS.read_text(encoding="utf-8").split("async def run_local_command", 1)[1].split(
        "def _load_guard_file_write", 1
    )[0]
    assert "ATRA_ALLOW_GIT_PUSH" in fn or "_allow_git_push" in fn
    assert "_is_git_push_command" in fn or "git push" in fn.lower()


@pytest.mark.asyncio
async def test_run_local_command_refuses_git_push(monkeypatch):
    mod = _load_tools()
    called = []

    def fake_run(*args, **kwargs):
        called.append(args)
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.delenv("ATRA_ALLOW_GIT_PUSH", raising=False)
    out = await mod.SystemTools.run_local_command("git push origin main")
    assert "ATRA_ALLOW_GIT_PUSH" in out
    assert called == []
    out2 = await mod.SystemTools.run_local_command("git -C /tmp/repo push")
    assert "ATRA_ALLOW_GIT_PUSH" in out2
    chained = await mod.SystemTools.run_local_command("git status && git push")
    assert "ATRA_ALLOW_GIT_PUSH" in chained


@pytest.mark.asyncio
async def test_run_local_command_allows_git_status(monkeypatch):
    mod = _load_tools()

    class _R:
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _R())
    monkeypatch.delenv("ATRA_ALLOW_GIT_PUSH", raising=False)
    out = await mod.SystemTools.run_local_command("git status --short")
    assert "STDOUT: ok" in out


@pytest.mark.asyncio
async def test_run_local_command_git_push_when_allow_env(monkeypatch):
    mod = _load_tools()

    class _R:
        stdout = "pushed"
        stderr = ""

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _R())
    monkeypatch.setenv("ATRA_ALLOW_GIT_PUSH", "true")
    out = await mod.SystemTools.run_local_command("git push origin main")
    assert "STDOUT: pushed" in out


def test_is_git_push_detects_bash_c_and_not_echo():
    mod = _load_tools()
    assert mod._is_git_push_command("bash -c 'git push origin main'")
    assert mod._is_git_push_command('sh -c "git push"')
    assert mod._is_git_push_command("bash -c git push")
    assert not mod._is_git_push_command("echo git push")
    assert not mod._is_git_push_command("bash -c 'git status'")


@pytest.mark.asyncio
async def test_run_local_command_refuses_bash_c_git_push(monkeypatch):
    mod = _load_tools()
    called = []

    def fake_run(*args, **kwargs):
        called.append(args)
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.delenv("ATRA_ALLOW_GIT_PUSH", raising=False)
    out = await mod.SystemTools.run_local_command("bash -c 'git push origin main'")
    assert "ATRA_ALLOW_GIT_PUSH" in out
    assert called == []


def test_ssh_run_source_blocks_git_push():
    fn = _TOOLS.read_text(encoding="utf-8").split("async def run_ssh_command", 1)[1].split(
        "async def read_project_file", 1
    )[0]
    assert "_is_git_push_command" in fn
    assert "ATRA_ALLOW_GIT_PUSH" in fn or "_allow_git_push" in fn


@pytest.mark.asyncio
async def test_ssh_run_refuses_git_push(monkeypatch):
    mod = _load_tools()
    called = []

    def fake_run(*args, **kwargs):
        called.append(args)
        raise AssertionError("ssh must not run")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.delenv("ATRA_ALLOW_GIT_PUSH", raising=False)
    out = await mod.SystemTools.run_ssh_command(
        "example.test", "git push origin main", user="u", password="p"
    )
    assert "ATRA_ALLOW_GIT_PUSH" in out
    assert called == []


def test_is_git_push_detects_python_c_and_not_print():
    mod = _load_tools()
    assert mod._is_git_push_command("python -c \"os.system('git push')\"")
    assert mod._is_git_push_command("python3 -c \"os.system('git push origin main')\"")
    assert mod._is_git_push_command("python -c \"subprocess.run(['git', 'push'])\"")
    assert not mod._is_git_push_command("python -c \"print('git push')\"")
    assert not mod._is_git_push_command("python -c \"os.system('git status')\"")


@pytest.mark.asyncio
async def test_run_local_command_refuses_python_c_git_push(monkeypatch):
    mod = _load_tools()
    called = []

    def fake_run(*args, **kwargs):
        called.append(args)
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.delenv("ATRA_ALLOW_GIT_PUSH", raising=False)
    out = await mod.SystemTools.run_local_command("python -c \"os.system('git push')\"")
    assert "ATRA_ALLOW_GIT_PUSH" in out
    assert called == []
    ssh = await mod.SystemTools.run_ssh_command(
        "example.test",
        "python3 -c \"os.system('git push')\"",
        user="u",
        password="p",
    )
    assert "ATRA_ALLOW_GIT_PUSH" in ssh
    assert called == []


def test_is_git_push_detects_node_e_and_not_console_log():
    mod = _load_tools()
    assert mod._is_git_push_command(
        "node -e \"require('child_process').execSync('git push')\""
    )
    assert mod._is_git_push_command(
        "node -e \"require('child_process').spawnSync('git', ['push'])\""
    )
    assert mod._is_git_push_command("nodejs --eval 'git push origin main'")
    assert not mod._is_git_push_command("node -e \"console.log('git push')\"")
    assert not mod._is_git_push_command("node -e \"console.log('hello')\"")


def test_is_git_push_detects_perl_e_and_not_print():
    mod = _load_tools()
    assert mod._is_git_push_command("perl -e 'system(\"git push\")'")
    assert mod._is_git_push_command("perl -e 'exec \"git push origin main\"'")
    assert not mod._is_git_push_command("perl -e 'print \"git push\"'")
    assert not mod._is_git_push_command("perl -e 'print \"hello\"'")


@pytest.mark.asyncio
async def test_run_local_command_refuses_node_and_perl_git_push(monkeypatch):
    mod = _load_tools()
    called = []

    def fake_run(*args, **kwargs):
        called.append(args)
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.delenv("ATRA_ALLOW_GIT_PUSH", raising=False)
    node = await mod.SystemTools.run_local_command(
        "node -e \"require('child_process').execSync('git push')\""
    )
    assert "ATRA_ALLOW_GIT_PUSH" in node
    perl = await mod.SystemTools.run_local_command("perl -e 'system(\"git push\")'")
    assert "ATRA_ALLOW_GIT_PUSH" in perl
    assert called == []
