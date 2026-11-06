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
