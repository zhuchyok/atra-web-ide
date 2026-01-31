"""
Unit tests for Skill Registry
"""

import pytest
import tempfile
import os
from pathlib import Path

from app.skill_registry import SkillRegistry, Skill, SkillSource, SkillMetadata


def test_skill_registry_initialization():
    """Test Skill Registry initialization"""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = SkillRegistry(
            bundled_skills_dir=tmpdir,
            managed_skills_dir=tmpdir
        )
        
        assert registry is not None
        assert len(registry.skills) == 0


def test_skill_registry_load_skills():
    """Test loading skills from directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Создаем тестовый skill
        skill_dir = Path(tmpdir) / "test_skill"
        skill_dir.mkdir()
        
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: Test skill
version: 1.0.0
---

# Test Skill

Test skill description.
""")
        
        registry = SkillRegistry(
            bundled_skills_dir=tmpdir,
            managed_skills_dir=tmpdir
        )
        
        registry.load_skills()
        
        # Проверяем, что skill загружен
        assert len(registry.skills) > 0
        skill = registry.get_skill("test-skill")
        assert skill is not None
        assert skill.name == "test-skill"


def test_skill_registry_get_skill():
    """Test getting skill by name"""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = SkillRegistry(
            bundled_skills_dir=tmpdir,
            managed_skills_dir=tmpdir
        )
        
        # Создаем и регистрируем skill
        skill = Skill(
            name="test-skill",
            description="Test",
            category="test",
            handler=None,
            parameters={},
            examples=[],
            version="1.0.0",
            created_at=None,
            source=SkillSource.BUILTIN,
            metadata=SkillMetadata(
                name="test-skill",
                description="Test"
            ),
            skill_path=str(tmpdir),
            instructions="Test instructions"
        )
        
        registry.register_skill(skill)
        
        # Получаем skill
        retrieved = registry.get_skill("test-skill")
        assert retrieved is not None
        assert retrieved.name == "test-skill"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
