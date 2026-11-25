"""Wave2 polish: mutate git tools must not be advertised until approve-wired."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXECUTOR = ROOT / "src" / "agents" / "core" / "executor.py"
VICTORIA = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"

_MUTATE = (
    "git_branch_create",
    "git_add",
    "git_commit",
    "git_pr_create",
    "git_test_run",
    "git_push",
)
_READ = ("git_status", "git_diff", "git_log", "git_pr_list")


def _allowed_tools_block() -> str:
    text = EXECUTOR.read_text(encoding="utf-8")
    return text.split("ALLOWED_TOOLS = {", 1)[1].split("}", 1)[0]


def test_allowed_tools_has_git_read_only():
    block = _allowed_tools_block()
    for name in _READ:
        assert f'"{name}"' in block, name


def test_allowed_tools_excludes_git_mutate():
    block = _allowed_tools_block()
    for name in _MUTATE:
        assert f'"{name}"' not in block, name


def test_system_prompt_list_uses_hint_not_hardcoded_mutate():
    text = EXECUTOR.read_text(encoding="utf-8")
    # Prompt builds from ALLOWED_TOOLS_HINT (mutate only if env on at import).
    assert "ALLOWED_TOOLS_HINT" in text.split("СПИСОК ДОПУСТИМЫХ TOOL:", 1)[1][:80]
    block = _allowed_tools_block()
    for name in _MUTATE:
        assert f'"{name}"' not in block, name
    assert '"git_pr_list"' in block


def test_victoria_registers_mutate_only_behind_env_gate():
    region = VICTORIA.read_text(encoding="utf-8")
    assert 'self.add_tool("git_pr_list", GitTools.git_pr_list)' in region
    assert 'self.add_tool("git_status", GitTools.git_status)' in region
    assert "if _allow_git_mutate():" in region
    # Mutate registrations live only inside the env gate.
    gated = region.split("if _allow_git_mutate():", 1)[1].split("\n        self.", 1)[0]
    for name in ("git_add", "git_commit", "git_branch_create", "git_pr_create"):
        assert f'add_tool("{name}"' in gated, name
    before = region.split("if _allow_git_mutate():", 1)[0]
    assert 'add_tool("git_add"' not in before
