import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
APP_ROOT = os.path.join(ROOT, "knowledge_os", "app")
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)


def test_adopt_does_not_mutate_slot_identity(monkeypatch):
    monkeypatch.setenv("WORKER_TASK_ISOLATION", "true")
    from task_isolation import isolation_enabled, resolve_adopt_identity

    assert isolation_enabled() is True
    slot = "Инна"
    run, slot_out, action = resolve_adopt_identity(slot, "Ксения", True)
    assert action == "adopt"
    assert run == "Ксения"
    assert slot_out == "Инна"

    run2, slot2, action2 = resolve_adopt_identity(slot_out, None, True)
    assert action2 == "own"
    assert run2 == "Инна"
    assert slot2 == "Инна"


def test_isolation_off_loop_still_exposes_old_mutation(monkeypatch):
    """Document rollback path: WORKER_TASK_ISOLATION=false may reassign loop identity."""
    monkeypatch.setenv("WORKER_TASK_ISOLATION", "false")
    from task_isolation import isolation_enabled, resolve_adopt_identity

    assert isolation_enabled() is False
    expert_name = "Инна"
    run, slot, action = resolve_adopt_identity(expert_name, "Ксения", True)
    assert action == "adopt"
    expert_name = run  # old worker_loop assignment
    run2, slot2, _ = resolve_adopt_identity(expert_name, None, True)
    assert run2 == "Ксения"
    assert slot2 == "Ксения"


@pytest.mark.asyncio
async def test_context_does_not_leak_between_binds():
    from task_isolation import bind_task_context, current_task_context

    assert current_task_context() is None
    async with bind_task_context("task-A", "Инна", source="overflow"):
        ctx_a = current_task_context()
        assert ctx_a is not None
        assert ctx_a.task_id == "task-A"
        assert ctx_a.expert_name == "Инна"
    async with bind_task_context("task-B", "Ксения", source="overflow"):
        ctx_b = current_task_context()
        assert ctx_b is not None
        assert ctx_b.task_id == "task-B"
        assert ctx_b.expert_name == "Ксения"
        assert ctx_b.task_id != "task-A"
    assert current_task_context() is None


def test_filter_drops_foreign_expert_keeps_generic(monkeypatch):
    monkeypatch.setenv("RAG_NAMESPACE_FILTER", "true")
    from task_isolation import filter_namespace_rows, push_task_context, reset_task_context

    rows = [
        {
            "content": "KSENIA_SECRET_MARKER",
            "metadata": {"expert_name": "Ксения", "source": "indexing_daemon"},
            "similarity": 0.91,
        },
        {
            "content": "project README",
            "metadata": {"source": "indexing_daemon", "file_path": "README.md"},
            "similarity": 0.80,
        },
        {
            "content": "YULIA_SECRET_MARKER",
            "metadata": {"expert_name": "Юлия", "source": "indexing_daemon"},
            "similarity": 0.95,
        },
    ]
    token = push_task_context("task-b", "Ксения")
    try:
        kept = filter_namespace_rows(rows)
    finally:
        reset_task_context(token)
    contents = [r["content"] for r in kept]
    assert "KSENIA_SECRET_MARKER" in contents
    assert "project README" in contents
    assert "YULIA_SECRET_MARKER" not in contents


def test_filter_disabled_keeps_foreign(monkeypatch):
    monkeypatch.setenv("RAG_NAMESPACE_FILTER", "false")
    from task_isolation import filter_namespace_rows

    rows = [
        {"content": "YULIA_SECRET_MARKER", "metadata": {"expert_name": "Юлия"}},
        {"content": "project README", "metadata": {}},
    ]
    kept = filter_namespace_rows(rows, expert_name="Ксения")
    assert len(kept) == 2


def test_judge_skip_on_task_id_mismatch():
    from task_isolation import judge_should_skip

    question = "[task_id:task-A] Сколько инцидентов в attack_report?"
    answer = "[task_id:task-B] PgBouncer default_pool_size=40"
    assert judge_should_skip(question=question, answer=answer) is True
    assert (
        judge_should_skip(
            question="same task",
            answer="ok",
            question_task_id="task-A",
            answer_task_id="task-A",
        )
        is False
    )


def test_judge_skip_when_answer_belongs_to_other_current_task():
    from task_isolation import judge_should_skip

    assert (
        judge_should_skip(
            question="операционный вопрос",
            answer="[task_id:other] чужой ответ",
            current_task_id="current",
        )
        is True
    )


def test_judge_skip_empty_answer_is_not_a_high_score():
    from task_isolation import judge_should_skip

    # Empty answer is not a mismatch; the gate itself must fail-open instead of scoring 10.
    assert (
        judge_should_skip(question="[task_id:task-A] q", answer="", current_task_id="task-A")
        is False
    )
