import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from knowledge_os.app.ai_core import TeamDiscussionEngine

@pytest.mark.asyncio
async def test_get_expert_styles():
    """Test that expert styles are correctly extracted and cached."""
    engine = TeamDiscussionEngine()
    
    # Test with known experts from TEAM_PERSONALITIES.md
    # We use partial matches to test fuzzy matching
    experts = ["Igor", "Anna", "Victoria", "NonExistentExpert"]
    
    styles = engine._get_expert_styles(experts)
    
    assert "### Igor Style:" in styles
    assert "### Anna Style:" in styles
    assert "### Victoria Style:" in styles
    assert "### NonExistentExpert Style:" in styles
    
    # Verify content for Igor (Backend Developer)
    assert "Техничный" in styles or "технический" in styles.lower()
    # Verify fallback for NonExistentExpert
    assert "Professional, technical, and focused on the task." in styles

@pytest.mark.asyncio
async def test_generate_discussion_mocked():
    """Test discussion generation with a mocked router."""
    mock_router = AsyncMock()
    mock_router.run_local_llm.return_value = ("**Victoria:** Hello team.\n**Igor:** Checking imports...", None)
    
    engine = TeamDiscussionEngine(router=mock_router)
    
    task_title = "Fix Import Bug"
    task_description = "The system fails to import 'state' module."
    experts = ["Victoria", "Igor"]
    context_data = "Error: ModuleNotFoundError: No module named 'state'"
    
    result = await engine.generate_discussion(
        task_title=task_title,
        task_description=task_description,
        experts=experts,
        context_data=context_data
    )
    
    assert "**Victoria:**" in result
    assert "**Igor:**" in result
    
    # Verify router was called with correct parameters
    args, kwargs = mock_router.run_local_llm.call_args
    prompt = args[0]
    assert task_title in prompt
    assert task_description in prompt
    assert "Victoria" in prompt
    assert "Igor" in prompt
    assert context_data in prompt
    assert kwargs["category"] == "team_discussion"

@pytest.mark.asyncio
async def test_generate_discussion_empty_response():
    """Test handling of empty response from router."""
    mock_router = AsyncMock()
    mock_router.run_local_llm.return_value = (None, None)
    
    engine = TeamDiscussionEngine(router=mock_router)
    result = await engine.generate_discussion("Title", "Desc", ["Igor"])
    
    assert "Failed to generate team discussion locally" in result
