import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_os.app.meta_architect import MetaArchitect


@pytest.mark.asyncio
async def test_meta_architect_graphrag_integration():
    """
    Verify that MetaArchitect successfully fetches and uses GraphRAG context during the evolution cycle.
    """
    # 1. Setup Mock Data
    mock_hot_spot = {
        "module_name": "test_module",
        "function_name": "test_function",
        "avg_time": 150.0,
        "call_count": 100,
        "failure_count": 0,
    }

    mock_graph_context = "🌐 [GRAPHRAG GLOBAL CONTEXT]: test_function is called by main_loop and depends on database_service."

    mock_hypothesis_json = json.dumps(
        {
            "analysis": "Function is slow due to DB overhead.",
            "mutation_hypothesis": "Implement caching for DB results.",
            "expected_improvement_percent": 30,
            "dependency_impact": "Reduces load on database_service.",
        }
    )

    mock_original_code = "def test_function():\n    return 'original'"
    mock_mutated_code = "def test_function():\n    # Mutated with caching\n    return 'mutated'"

    # 2. Mock Dependencies
    mock_profiler = AsyncMock()
    mock_profiler.get_hot_spots.return_value = [mock_hot_spot]

    mock_graphrag = AsyncMock()
    mock_graphrag.retrieve_graph_context.return_value = mock_graph_context

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.close = AsyncMock()

    # 3. Patch and Run
    with (
        patch("knowledge_os.app.meta_architect.get_profiler", return_value=mock_profiler),
        patch("knowledge_os.app.meta_architect.get_graphrag_service", return_value=mock_graphrag),
        patch("knowledge_os.app.meta_architect.run_smart_agent_async") as mock_agent,
        patch("knowledge_os.app.meta_architect.run_optimization_cycle", new_callable=AsyncMock),
        patch("asyncpg.connect", return_value=mock_conn),
        patch("os.path.exists", return_value=True),
        patch("builtins.open", patch("builtins.open", MagicMock())),
    ):
        # Setup mock agent responses for hypothesis and mutation
        mock_agent.side_effect = [
            mock_hypothesis_json,  # First call: hypothesis
            f"```python\n{mock_mutated_code}\n```",  # Second call: mutation
        ]

        # Mock file reading
        with patch("knowledge_os.app.meta_architect.open", MagicMock()) as mock_open:
            mock_file = MagicMock()
            mock_file.read.return_value = mock_original_code
            mock_open.return_value.__enter__.return_value = mock_file

            architect = MetaArchitect()
            await architect.self_evolution_cycle()

            # 4. Verifications

            # Verify GraphRAG was called with correct query
            mock_graphrag.retrieve_graph_context.assert_called_once_with(
                "module test_module function test_function"
            )

            # Verify hypothesis prompt contained GraphRAG context
            hypothesis_call_args = mock_agent.call_args_list[0]
            hypothesis_prompt = hypothesis_call_args[0][0]
            assert mock_graph_context in hypothesis_prompt
            assert "Используя данные GraphRAG выше" in hypothesis_prompt
            assert "dependency_impact" in hypothesis_prompt

            # Verify mutation prompt contained GraphRAG context
            mutation_call_args = mock_agent.call_args_list[1]
            mutation_prompt = mutation_call_args[0][0]
            assert mock_graph_context in mutation_prompt
            assert (
                "Учитывайте зависимости и логические связи, указанные в контексте GraphRAG"
                in mutation_prompt
            )

            # Verify DB logging
            assert mock_conn.execute.call_count >= 1
            db_call_args = mock_conn.execute.call_args[0]
            assert "INSERT INTO knowledge_nodes" in db_call_args[0]
            assert "test_module.test_function" in db_call_args[1]


if __name__ == "__main__":
    asyncio.run(test_meta_architect_graphrag_integration())
