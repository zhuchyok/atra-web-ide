"""Upstream guards: no Unknown Expert mentorship / no junk SOP titles."""

from app.mentorship_engine import resolve_mentorship_expert_name
from app.sop_generator import resolve_sop_process_title


class TestMentorshipExpertResolve:
    def test_from_assignee_name(self):
        assert (
            resolve_mentorship_expert_name(
                title="any",
                metadata={},
                assignee_name="Даниил",
            )
            == "Даниил"
        )

    def test_from_delegated_title(self):
        assert (
            resolve_mentorship_expert_name(
                title="🤖 Делегировано: Лиза (main)",
                metadata={},
                assignee_name=None,
            )
            == "Лиза"
        )

    def test_rejects_unknown(self):
        assert (
            resolve_mentorship_expert_name(
                title="completed task",
                metadata={"expert_name": "Unknown Expert"},
                assignee_name=None,
            )
            is None
        )


class TestSopProcessTitle:
    def test_parent_goal_wins(self):
        assert (
            resolve_sop_process_title(
                title="🤖 Делегировано: Марина (x)",
                description="noise",
                metadata={"parent_goal": "проверь файл /app/foo.py на pip install"},
            )
            == "проверь файл /app/foo.py на pip install"
        )

    def test_skips_delegated_without_goal(self):
        assert (
            resolve_sop_process_title(
                title="🤖 Делегировано: Николай (abc)",
                description="short",
                metadata={},
            )
            is None
        )

    def test_plain_title_ok(self):
        assert (
            resolve_sop_process_title(
                title="Настроить бэкап Postgres",
                description="",
                metadata={},
            )
            == "Настроить бэкап Postgres"
        )
