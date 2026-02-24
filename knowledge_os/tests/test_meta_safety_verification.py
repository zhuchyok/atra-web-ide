import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_os.app.meta_architect import MetaArchitect


@pytest.mark.asyncio
async def test_verify_mutation_safety_safe_change():
    """Test safety verification for a safe optimization (no signature change)."""
    architect = MetaArchitect()

    module_name = "test_module"
    function_name = "test_func"
    mutated_code = """
def test_func(a, b):
    # Optimized version
    return a + b
"""

    # Mocking GraphRAG and run_smart_agent_async
    with (
        patch("knowledge_os.app.meta_architect.get_graphrag_service") as mock_get_graphrag,
        patch("knowledge_os.app.meta_architect.run_smart_agent_async") as mock_run_agent,
        patch("asyncpg.connect") as mock_connect,
    ):
        # Mock DB connection and fetch
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        mock_conn.fetchval.return_value = "node-uuid"
        mock_conn.fetch.return_value = [{"content": "caller()", "file_path": "caller.py"}]

        # Mock AI response
        mock_run_agent.return_value = json.dumps(
            {"safety_score": 0.9, "risks": [], "recommendation": "proceed"}
        )

        report = await architect.verify_mutation_safety(module_name, function_name, mutated_code)

        assert report["score"] == 0.9
        assert report["recommendation"] == "proceed"
        assert len(report["risks"]) == 0


@pytest.mark.asyncio
async def test_verify_mutation_safety_unsafe_change():
    """Test safety verification for an unsafe change (breaking signature)."""
    architect = MetaArchitect()

    module_name = "test_module"
    function_name = "test_func"
    # Added a new mandatory argument 'c'
    mutated_code = """
def test_func(a, b, c):
    return a + b + c
"""

    with (
        patch("knowledge_os.app.meta_architect.get_graphrag_service") as mock_get_graphrag,
        patch("knowledge_os.app.meta_architect.run_smart_agent_async") as mock_run_agent,
        patch("asyncpg.connect") as mock_connect,
    ):
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        mock_conn.fetchval.return_value = "node-uuid"
        mock_conn.fetch.return_value = [{"content": "test_func(1, 2)", "file_path": "caller.py"}]

        # Mock AI response for unsafe change
        mock_run_agent.return_value = json.dumps(
            {
                "safety_score": 0.2,
                "risks": [
                    "Breaking signature: added mandatory argument 'c' without updating callers"
                ],
                "recommendation": "abort",
            }
        )

        report = await architect.verify_mutation_safety(module_name, function_name, mutated_code)

        assert report["score"] == 0.2
        assert report["recommendation"] == "abort"
        assert "Breaking signature" in report["risks"][0]


@pytest.mark.asyncio
async def test_verify_mutation_safety_function_not_found():
    """Test safety verification when the function is missing in mutated code."""
    architect = MetaArchitect()

    module_name = "test_module"
    function_name = "missing_func"
    mutated_code = """
def other_func():
    pass
"""

    report = await architect.verify_mutation_safety(module_name, function_name, mutated_code)

    assert report["score"] == 0.0
    assert "not found" in report["risks"][0]
