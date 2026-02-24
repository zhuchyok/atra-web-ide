import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_os.app.expert_evolver import evolve_experts


@pytest.mark.asyncio
async def test_graphrag_context_injection():
    """
    Verify that GraphRAG context is correctly fetched and injected into the mutation prompt.
    """
    # Mock data
    mock_expert = {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "name": "TestExpert",
        "role": "Tester",
        "system_prompt": "Original prompt",
        "version": 1,
        "total_usage": 10,
    }

    mock_feedback = [
        {"user_query": "test q", "assistant_response": "test a", "feedback_score": 5, "error": None}
    ]

    mock_graph_context = "🌐 [GRAPHRAG GLOBAL CONTEXT]: TestExpert interacts with Igor on testing."

    # Mock database connection
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = [
        [mock_expert],  # experts query
        mock_feedback,  # interaction_logs query
    ]
    mock_conn.execute = AsyncMock()
    mock_conn.close = AsyncMock()

    # Mock GraphRAG service
    mock_graphrag = AsyncMock()
    mock_graphrag.retrieve_graph_context.return_value = mock_graph_context

    # Mock LocalAIRouter and mutation generation
    mock_result_json = json.dumps(
        {
            "new_prompt": "Evolved prompt with GraphRAG knowledge and some very long text to pass validation. "
            * 5,
            "assigned_skills": ["test-skill"],
            "reasoning": "Because of GraphRAG context",
        }
    )

    with (
        patch("asyncpg.connect", return_value=mock_conn),
        patch("knowledge_os.app.expert_evolver.get_graphrag_service", return_value=mock_graphrag),
        patch(
            "knowledge_os.app.expert_evolver.run_local_mutation_agent", new_callable=AsyncMock
        ) as mock_agent,
        patch("os.path.exists", return_value=True),
        patch("os.path.isdir", return_value=True),
        patch("os.listdir", side_effect=lambda path: ["skill1"] if "skills" in path else []),
    ):
        mock_agent.return_value = mock_result_json

        # Run evolution for specific expert
        await evolve_experts(expert_name="TestExpert")

        # Verify GraphRAG was called with correct query
        mock_graphrag.retrieve_graph_context.assert_called_once()
        call_args = mock_graphrag.retrieve_graph_context.call_args[0][0]
        assert "TestExpert" in call_args

        # Verify mutation agent was called with prompt containing GraphRAG context
        mock_agent.assert_called_once()
        evolution_prompt = mock_agent.call_args[0][0]
        assert mock_graph_context in evolution_prompt
        assert "ВЫ - ГЛАВНЫЙ АРХИТЕКТОР ТАЛАНТОВ (УРОВЕНЬ 6)" in evolution_prompt
        assert "положение эксперта в графе знаний (GraphRAG)" in evolution_prompt

        # Verify DB update
        mock_conn.execute.assert_called_once()
        update_args = mock_conn.execute.call_args[0]
        assert "UPDATE experts" in update_args[0]
        assert "Evolved prompt with GraphRAG knowledge" in update_args[1]


if __name__ == "__main__":
    asyncio.run(test_graphrag_context_injection())
