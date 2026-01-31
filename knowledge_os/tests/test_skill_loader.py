"""
Unit tests for Skill Loader
"""

import pytest
import asyncio
import tempfile
from pathlib import Path

from app.skill_loader import SkillLoader
from app.skill_registry import SkillRegistry, get_skill_registry


@pytest.mark.asyncio
async def test_skill_loader_initialization():
    """Test Skill Loader initialization"""
    registry = get_skill_registry()
    loader = SkillLoader(skill_registry=registry)
    
    assert loader is not None
    assert loader.skill_registry == registry


@pytest.mark.asyncio
async def test_skill_loader_load_all_skills():
    """Test loading all skills"""
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
""")
        
        registry = SkillRegistry(
            bundled_skills_dir=tmpdir,
            managed_skills_dir=tmpdir
        )
        
        loader = SkillLoader(skill_registry=registry)
        await loader.load_all_skills()
        
        # Проверяем, что skill загружен
        assert len(registry.skills) > 0


@pytest.mark.asyncio
async def test_skill_loader_watcher():
    """Test Skills Watcher"""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = SkillRegistry(
            bundled_skills_dir=tmpdir,
            managed_skills_dir=tmpdir
        )
        
        loader = SkillLoader(skill_registry=registry)
        
        await loader.start_watcher()
        assert loader.is_watching()
        
        await loader.stop_watcher()
        assert not loader.is_watching()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
