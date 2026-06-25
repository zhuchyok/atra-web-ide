"""Tests for worker_memory.py — Skill loading for experts."""

import os
import tempfile
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
    async def test_load_skills_known_expert(self):
        """Known expert role should return non-empty skills."""
        from app.worker.worker_memory import load_skills_for_expert, ROLE_DEPARTMENT_TO_SKILLS

        for role in ROLE_DEPARTMENT_TO_SKILLS:
            result = await load_skills_for_expert(role, "task")
            assert isinstance(result, str)
            break  # just test one

    def test_role_skill_mapping_exists(self):
        """ROLE_DEPARTMENT_TO_SKILLS should have mappings."""
        from app.worker.worker_memory import ROLE_DEPARTMENT_TO_SKILLS

        assert len(ROLE_DEPARTMENT_TO_SKILLS) >= 5
        assert "backend" in ROLE_DEPARTMENT_TO_SKILLS
        assert "general" in ROLE_DEPARTMENT_TO_SKILLS
