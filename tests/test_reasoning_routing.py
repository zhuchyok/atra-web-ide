import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

# Add knowledge_os/app to sys.path
sys.path.append(os.path.join(os.getcwd(), "knowledge_os", "app"))

from ai_core import _run_cloud_agent_async

@pytest.mark.asyncio
async def test_run_cloud_agent_async_preserves_category():
    """
    Verifies that _run_cloud_agent_async passes the correct category and is_vip
    to LocalAIRouter.run_local_llm.
    """
    prompt = "Test prompt"
    category = "reasoning"
    is_vip = True

    # Mock LocalAIRouter
    with patch("ai_core.LocalAIRouter") as MockRouter:
        mock_router_instance = MockRouter.return_value
        mock_router_instance.check_health = AsyncMock(return_value=[{"name": "test_node"}])
        mock_router_instance.run_local_llm = AsyncMock(return_value=("Mock response", "test_source"))

        response = await _run_cloud_agent_async(prompt, category=category, is_vip=is_vip)

        # Verify run_local_llm was called with the correct arguments
        mock_router_instance.run_local_llm.assert_called_once()
        args, kwargs = mock_router_instance.run_local_llm.call_args
        assert kwargs.get("category") == category
        assert kwargs.get("is_vip") == is_vip
        assert response == "Mock response"

if __name__ == "__main__":
    asyncio.run(test_run_cloud_agent_async_preserves_category())
