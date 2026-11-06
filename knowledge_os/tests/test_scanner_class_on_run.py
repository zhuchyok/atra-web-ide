"""v150.99: /run keeps scanner_class; BaseAgent.run honors blocked_tools."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_task_request_has_scanner_class_field():
    text = (ROOT / "src" / "agents" / "bridge" / "victoria_server.py").read_text(encoding="utf-8")
    chunk = text.split("class TaskRequest", 1)[1].split("class TaskResponse", 1)[0]
    assert "scanner_class" in chunk


def test_victoria_run_passes_blocked_tools_to_super():
    text = (ROOT / "src" / "agents" / "bridge" / "victoria_server.py").read_text(encoding="utf-8")
    fn = text.split("async def run(\n        self,", 1)[1].split(
        "def _extract_last_answer_from_long", 1
    )[0]
    assert "blocked_tools" in fn
    assert "blocked_tools=blocked_tools" in fn
    assert "_blocked_tools_for_scanner_class" in text


def test_base_agent_run_seeds_blocked_tools():
    text = (ROOT / "src" / "agents" / "core" / "base_agent.py").read_text(encoding="utf-8")
    fn = text.split("async def run(", 1)[1].split("Превышен лимит шагов", 1)[0]
    assert "blocked_tools" in fn
    assert "agent._blocked_tools[tool]" in fn


def test_victoria_fallback_human_blocks_shell():
    text = (ROOT / "src" / "agents" / "bridge" / "victoria_server.py").read_text(
        encoding="utf-8"
    )
    fn = text.split("def _blocked_tools_for_scanner_class", 1)[1].split(
        "def _format_ide_context", 1
    )[0]
    for name in (
        "run_terminal_cmd",
        "ssh_run",
        "git_add",
        "git_commit",
        "git_branch_create",
        "git_pr_create",
    ):
        assert name in fn
    human_list = fn.split('if k in ("human", "runbook")', 1)[1].split("elif k ==", 1)[0]
    assert "run_terminal_cmd" in human_list
    patch_list = fn.split('elif k == "patch"', 1)[1].split("else:", 1)[0]
    assert "run_terminal_cmd" not in patch_list
    assert "git_push" in patch_list


def test_victoria_run_gates_patch_handoff():
    text = (ROOT / "src" / "agents" / "bridge" / "victoria_server.py").read_text(
        encoding="utf-8"
    )
    assert "scanner_patch_handoff_rejected" in text
    assert "cannot HANDOFF" in text
