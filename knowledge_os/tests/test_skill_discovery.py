"""
Unit tests for Skill Discovery
"""

import pytest
import asyncio
import tempfile
from pathlib import Path

from app.skill_discovery import SkillDiscovery
from app.skill_registry import SkillRegistry, get_skill_registry


@pytest.mark.asyncio
async def test_skill_discovery_initialization():
    """Test Skill Discovery initialization"""
    registry = get_skill_registry()
    discovery = SkillDiscovery(skill_registry=registry)
    
    assert discovery is not None
    assert discovery.skill_registry == registry


@pytest.mark.asyncio
async def test_skill_discovery_extract_keywords():
    """Test keyword extraction"""
    registry = get_skill_registry()
    discovery = SkillDiscovery(skill_registry=registry)
    
    keywords = discovery._extract_keywords("отправка email через Gmail API")
    
    assert len(keywords) > 0
    assert "email" in keywords or "gmail" in keywords


@pytest.mark.asyncio
async def test_skill_discovery_generate_skill_name():
    """Test skill name generation"""
    registry = get_skill_registry()
    discovery = SkillDiscovery(skill_registry=registry)
    
    name = discovery._generate_skill_name(
        "отправка email через Gmail",
        {"name": "gmail-api"},
        None
    )
    
    assert name is not None
    assert len(name) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
