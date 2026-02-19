import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from knowledge_os.app.ai_core import _trigger_shadow_execution

@pytest.mark.asyncio
async def test_trigger_shadow_execution_no_mutations():
    """Test that it returns early if no mutations are found."""
    with patch('knowledge_os.app.ai_core._get_db_pool') as mock_pool:
        mock_conn = AsyncMock()
        mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
        
        # Mock expert_id
        with patch('knowledge_os.app.ai_core._get_expert_id', return_value="uuid-123"):
            # No mutations found
            mock_conn.fetch.return_value = []
            
            await _trigger_shadow_execution(
                prompt="Hello",
                expert_name="Victoria",
                production_response="Hi",
                request_id="req-1"
            )
            
            mock_conn.fetch.assert_called_once()
            # Verify no shadow execution happened (no further calls)

@pytest.mark.asyncio
async def test_trigger_shadow_execution_with_mutations():
    """Test that it triggers shadow execution when mutations are found."""
    with patch('knowledge_os.app.ai_core._get_db_pool') as mock_pool:
        mock_conn = AsyncMock()
        mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
        
        # Mock expert_id
        with patch('knowledge_os.app.ai_core._get_expert_id', return_value="uuid-123"):
            # Mutation found
            mock_conn.fetch.return_value = [
                {'id': 'mut-1', 'mutated_prompt': 'You are a better Victoria.'}
            ]
            
            # Mock shadow execution (local router)
            with patch('knowledge_os.app.ai_core.LocalAIRouter') as mock_router:
                mock_router_instance = mock_router.return_value
                mock_router_instance.run_local_llm = AsyncMock(return_value=("Shadow Hi", "local"))
                
                with patch('knowledge_os.app.ai_core.logger') as mock_logger:
                    await _trigger_shadow_execution(
                        prompt="Hello",
                        expert_name="Victoria",
                        production_response="Hi",
                        request_id="req-1"
                    )
                    
                    # Verify shadow execution was logged
                    mock_logger.info.assert_any_call("👻 [SHADOW] Found 1 shadow mutations for Victoria")
                    mock_logger.info.assert_any_call("⚖️ [SHADOW] Sending results for mutation mut-1 to evaluator (Placeholder)")
                    
                    # Verify router was called
                    mock_router_instance.run_local_llm.assert_called_once()
                    args, kwargs = mock_router_instance.run_local_llm.call_args
                    assert "You are a better Victoria." in args[0]
                    assert "Hello" in args[0]
