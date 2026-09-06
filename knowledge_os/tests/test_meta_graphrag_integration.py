import asyncio
import json
import os
from unittest.mock import MagicMock, patch

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
    class ProfilerStub:
        async def get_hot_spots(self, limit=3):
            return [mock_hot_spot]

    class GraphRagStub:
        def __init__(self):
            self.queries = []

        async def retrieve_graph_context(self, query):
            self.queries.append(query)
            return mock_graph_context

    class ConnStub:
        def __init__(self):
            self.execute_calls = []

        async def execute(self, *args, **kwargs):
            self.execute_calls.append((args, kwargs))

        async def close(self):
            return None

    mock_profiler = ProfilerStub()
    mock_graphrag = GraphRagStub()
    mock_conn = ConnStub()

    # 3. Patch and Run
    agent_prompts = []
    agent_outputs = [
        mock_hypothesis_json,  # First call: hypothesis
        f"```python\n{mock_mutated_code}\n```",  # Second call: mutation
    ]

    async def _mock_agent(prompt, **kwargs):
        agent_prompts.append(prompt)
        if agent_outputs:
            return agent_outputs.pop(0)
        return "ok"

    async def _noop_optimization_cycle():
        return None

    with (
        patch("knowledge_os.app.meta_architect.get_profiler", return_value=mock_profiler),
        patch("knowledge_os.app.meta_architect.get_graphrag_service", return_value=mock_graphrag),
        patch("knowledge_os.app.meta_architect.run_smart_agent_async", new=_mock_agent),
        patch("knowledge_os.app.meta_architect.run_optimization_cycle", new=_noop_optimization_cycle),
        patch("asyncpg.connect", return_value=mock_conn),
        patch("os.path.exists", return_value=True),
        patch("builtins.open", new=MagicMock()),
    ):
        # Mock file reading
        with patch("knowledge_os.app.meta_architect.open", MagicMock()) as mock_open:
            mock_file = MagicMock()
            mock_file.read.return_value = mock_original_code
            mock_open.return_value.__enter__.return_value = mock_file

            architect = MetaArchitect()
            await architect.self_evolution_cycle()

            # 4. Verifications

            # Verify GraphRAG was called with correct query
            assert mock_graphrag.queries == ["module test_module function test_function"]

            # Verify hypothesis prompt contained GraphRAG context
            hypothesis_prompt = agent_prompts[0]
            assert mock_graph_context in hypothesis_prompt
            assert "Используя данные GraphRAG выше" in hypothesis_prompt
            assert "dependency_impact" in hypothesis_prompt

            # Verify mutation prompt contained GraphRAG context
            mutation_prompt = agent_prompts[1]
            assert mock_graph_context in mutation_prompt
            assert (
                "Учитывайте зависимости и логические связи, указанные в контексте GraphRAG"
                in mutation_prompt
            )

            # Verify DB logging
            assert len(mock_conn.execute_calls) >= 1
            insert_calls = [
                call for call in mock_conn.execute_calls if "INSERT INTO knowledge_nodes" in str(call[0][0])
            ]
            assert insert_calls, "Expected INSERT INTO knowledge_nodes to be executed"
            first_insert_args = insert_calls[0][0]
            assert "test_module.test_function" in first_insert_args[1]


if __name__ == "__main__":
    asyncio.run(test_meta_architect_graphrag_integration())
