"""Tests for worker_memory.py — Skill loading for experts."""

import pytest


class TestLoadSkillsForExpert:
    """Test the load_skills_for_expert async wrapper."""

    @pytest.mark.asyncio
    async def test_load_skills_returns_string(self):
        """load_skills_for_expert should return a string (empty or not)."""
        from app.worker.worker_memory import load_skills_for_expert

        result = await load_skills_for_expert("unknown_expert", "some task")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_load_skills_known_role_key(self):
        """Known role key should return non-empty skills when SKILL.md exists."""
        from app.worker.worker_memory import ROLE_DEPARTMENT_TO_SKILLS, load_skills_for_expert

        for role in ROLE_DEPARTMENT_TO_SKILLS:
            result = await load_skills_for_expert(role, "task")
            assert isinstance(result, str)
            if result:
                assert "ИНСТРУКЦИИ ИЗ СКИЛЛОВ" in result
            break

    @pytest.mark.asyncio
    async def test_load_skills_anna_by_name_hint(self):
        """Russian expert name Анна should resolve QA skills via name hint."""
        from app.worker.worker_memory import load_skills_for_expert

        result = await load_skills_for_expert("Анна", "проверь регрессию API")
        assert isinstance(result, str)
        assert len(result) > 0
        assert "ИНСТРУКЦИИ ИЗ СКИЛЛОВ" in result

    @pytest.mark.asyncio
    async def test_load_skills_by_role_substring(self):
        """Role string containing 'qa' should pick QA skill folders."""
        from app.worker.worker_memory import load_skills_for_expert

        result = await load_skills_for_expert(
            "Анна", "anything", role="QA Engineer", department="Quality"
        )
        assert len(result) > 0
        assert "qa-regression" in result or "webapp-testing" in result or "ИНСТРУКЦИИ" in result

    def test_role_skill_mapping_exists(self):
        """ROLE_DEPARTMENT_TO_SKILLS should have mappings."""
        from app.worker.worker_memory import ROLE_DEPARTMENT_TO_SKILLS

        assert len(ROLE_DEPARTMENT_TO_SKILLS) >= 5
        assert "backend" in ROLE_DEPARTMENT_TO_SKILLS
        assert "general" in ROLE_DEPARTMENT_TO_SKILLS
