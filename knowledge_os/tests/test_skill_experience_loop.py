"""TDD: closed skill/experience loop for experts (Hermes-pattern borrow)."""

import os
from unittest.mock import AsyncMock, patch

import pytest


def test_skill_loop_flag_default_true(monkeypatch):
    monkeypatch.delenv("SKILL_LOOP_ENABLED", raising=False)
    from app.skill_experience_loop import is_skill_loop_enabled

    assert is_skill_loop_enabled() is True


def test_skill_loop_flag_off(monkeypatch):
    monkeypatch.setenv("SKILL_LOOP_ENABLED", "false")
    from app.skill_experience_loop import is_skill_loop_enabled

    assert is_skill_loop_enabled() is False


def test_append_experience_lessons_prepends_block():
    from app.skill_experience_loop import append_experience_lessons

    out = append_experience_lessons("Do the task", ["lesson-a", "lesson-b"])
    assert "lesson-a" in out
    assert "lesson-b" in out
    assert out.index("lesson-a") < out.index("Do the task")


def test_append_experience_lessons_empty_noop():
    from app.skill_experience_loop import append_experience_lessons

    assert append_experience_lessons("Do the task", []) == "Do the task"


@pytest.mark.asyncio
async def test_maybe_commit_skips_when_flag_off(monkeypatch):
    monkeypatch.setenv("SKILL_LOOP_ENABLED", "0")
    from app import skill_experience_loop as loop

    with patch.object(loop, "commit_experience_lesson", new_callable=AsyncMock) as commit:
        result = await loop.maybe_commit_expert_experience(
            goal="fix redis",
            result="restarted consumer group",
            expert_name="Сергей",
        )
    assert result is None
    commit.assert_not_called()


@pytest.mark.asyncio
async def test_maybe_commit_calls_commit_on_success(monkeypatch):
    monkeypatch.setenv("SKILL_LOOP_ENABLED", "true")
    from app import skill_experience_loop as loop

    with patch.object(
        loop,
        "commit_experience_lesson",
        new_callable=AsyncMock,
        return_value={"status": "ok", "node_id": "n1"},
    ) as commit:
        result = await loop.maybe_commit_expert_experience(
            goal="fix redis stream",
            result="consumer group recreated; backlog drained",
            expert_name="Сергей",
        )
    assert result == {"status": "ok", "node_id": "n1"}
    commit.assert_awaited_once()
    kwargs = commit.await_args.kwargs
    assert "fix redis stream" in kwargs["goal"]
    assert "Сергей" in kwargs["lesson"] or kwargs.get("expert_name") == "Сергей"
    assert kwargs["outcome"] == "passed"


def test_expert_worker_wires_skill_loop_read_and_write():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src_path = os.path.join(root, "knowledge_os", "app", "expert_worker.py")
    src = open(src_path, encoding="utf-8").read()

    assert "skill_experience_loop" in src
    assert "fetch_experience_lessons" in src
    assert "append_experience_lessons" in src
    assert "maybe_commit_expert_experience" in src
