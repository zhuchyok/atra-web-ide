from app.cursor_method import (
    CURSOR_METHOD_PROMPT,
    is_bare_done,
    should_journal_task,
)
from app.swarm_intelligence import SwarmAgent, SwarmIntelligence
from app.task_result_validator import validate_task_result


def test_bare_done_rejected():
    assert is_bare_done("готово")
    assert is_bare_done("всё работает")
    assert not is_bare_done("ok")
    assert not is_bare_done("готово. pytest 13 passed")
    ok, score = validate_task_result("проверь health", "готово")
    assert ok is False
    assert score <= 0.2


def test_fast_path_not_journaled():
    assert should_journal_task("Fast-path file check: x", "fast_path") is False
    assert should_journal_task("Task completed: audit", "success") is True


def test_swarm_island_prompt_has_cursor_method():
    swarm = SwarmIntelligence(swarm_size=1)
    agent = SwarmAgent(agent_id="a", agent_name="Agent_1", role="explorer")
    prompt = swarm._build_island_prompt(agent, "проверь очередь", 0)
    assert CURSOR_METHOD_PROMPT.strip() in prompt
    assert "готово" in prompt.lower()
