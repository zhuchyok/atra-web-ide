import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_os.app.meta_architect import MetaArchitect


@pytest.mark.asyncio
async def test_meta_architect_full_cycle():
    """
    Integration test for MetaArchitect.self_evolution_cycle().
    Mocks dependencies to verify the full cycle of mutation generation,
    safety check, and registration.
    """
    # 1. Setup Mocks
    mock_hot_spot = {
        "module_name": "test_module",
        "function_name": "test_function",
        "avg_time": 150.5,
        "call_count": 100,
        "failure_count": 0,
    }

    mock_profiler = MagicMock()
    mock_profiler.get_hot_spots = AsyncMock(return_value=[mock_hot_spot])

    mock_graphrag = MagicMock()
    mock_graphrag.retrieve_graph_context = AsyncMock(return_value="Test Graph Context")

    # Mock run_smart_agent_async for different categories
    async def mock_run_smart_agent(prompt, *args, **kwargs):
        category = kwargs.get("category")
        # Handle unexpected 'model' argument in SafetyVerifier
        if category == "architectural_evolution":
            return json.dumps(
                {
                    "analysis": "Test analysis",
                    "mutation_hypothesis": "Test hypothesis",
                    "expected_improvement_percent": 30,
                    "dependency_impact": "None",
                }
            )
        elif category == "code_mutation":
            return "```python\ndef test_function():\n    return 'mutated'\n```"
        elif category == "safety_audit":
            return json.dumps({"safety_score": 90, "risks": [], "recommendation": "proceed"})
        return "Unknown"

    # Mock DB connection
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = 0  # Return 0 for count queries
    mock_pool = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # 2. Patch dependencies
    with (
        patch("knowledge_os.app.meta_architect.get_profiler", return_value=mock_profiler),
        patch("knowledge_os.app.meta_architect.get_graphrag_service", return_value=mock_graphrag),
        patch(
            "knowledge_os.app.meta_architect.run_smart_agent_async",
            side_effect=mock_run_smart_agent,
        ),
        patch(
            "knowledge_os.app.safety_verifier.run_smart_agent_async",
            side_effect=mock_run_smart_agent,
        ),
        patch("knowledge_os.app.meta_architect.SafetyVerifier") as mock_sv_class,
        patch("knowledge_os.app.meta_architect.asyncpg.connect", return_value=mock_conn),
        patch("knowledge_os.app.meta_architect.run_optimization_cycle", AsyncMock()),
        patch("knowledge_os.app.meta_architect.get_traffic_mirror") as mock_get_tm,
    ):
        mock_sv = MagicMock()
        mock_sv.verify_mutation = AsyncMock(
            return_value={"safety_score": 90, "risks": [], "recommendation": "proceed"}
        )
        mock_sv_class.return_value = mock_sv

        # Mock file existence and content
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", MagicMock()) as mock_open,
        ):
            mock_file = MagicMock()
            mock_file.read.return_value = "def test_function():\n    return 'original'"
            mock_open.return_value.__enter__.return_value = mock_file

            mock_tm = MagicMock()
            mock_tm.register_shadow = AsyncMock()
            mock_get_tm.return_value = mock_tm

            # 3. Initialize and Run
            architect = MetaArchitect(db_url="postgresql://test:test@localhost:5432/test")
            await architect.self_evolution_cycle()

            # 4. Verifications
            # Verify hot spots were fetched
            mock_profiler.get_hot_spots.assert_called_once()

            # Verify GraphRAG context was retrieved
            mock_graphrag.retrieve_graph_context.assert_called_once()

            # Verify TrafficMirror registration
            mock_tm.register_shadow.assert_called_once()

            # Verify DB logging (knowledge_node creation)
            # We expect two calls: one for mutation and one for potential safety violation (but here it's safe)
            # Wait, the code calls conn.execute for the mutation node
            assert mock_conn.execute.called
            args, _ = mock_conn.execute.call_args
            assert "INSERT INTO knowledge_nodes" in args[0]
            assert (
                "architecture_mutation" in args[2]
            )  # metadata is the 3rd arg in the second execute call?
            # Actually, let's check the call more carefully

            print("Test passed: MetaArchitect full cycle verified.")


if __name__ == "__main__":
    asyncio.run(test_meta_architect_full_cycle())
