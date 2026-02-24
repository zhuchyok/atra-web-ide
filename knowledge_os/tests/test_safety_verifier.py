import asyncio
from unittest.mock import MagicMock, patch

import pytest

from knowledge_os.app.safety_verifier import SafetyVerifier


@pytest.mark.asyncio
async def test_safety_verifier_impact_analysis():
    # Mocking dependencies
    mock_db_url = "postgresql://test:test@localhost:5432/test_db"
    verifier = SafetyVerifier(mock_db_url)

    # Test data
    module_name = "test_module"
    function_name = "test_function"
    mutated_code = """
def test_function(a, b, c=None):
    return a + b
"""

    mock_dependencies = [
        {"name": "caller_a", "file_path": "caller_a.py", "content": "test_function(1, 2)"},
        {"name": "caller_b", "file_path": "caller_b.py", "content": "test_function(x, y)"},
    ]

    # Mocking _get_downstream_dependencies
    with patch.object(
        SafetyVerifier, "_get_downstream_dependencies", return_value=mock_dependencies
    ):
        # Mocking run_smart_agent_async
        mock_audit_json = """
```json
{
    "safety_score": 90,
    "risks": [],
    "recommendation": "proceed"
}
```
"""
        with patch(
            "knowledge_os.app.safety_verifier.run_smart_agent_async", return_value=mock_audit_json
        ):
            report = await verifier.verify_mutation(module_name, function_name, mutated_code)

            assert report["safety_score"] == 90
            assert report["recommendation"] == "proceed"
            assert len(report["risks"]) == 0


@pytest.mark.asyncio
async def test_safety_verifier_risk_detection():
    verifier = SafetyVerifier()

    module_name = "test_module"
    function_name = "test_function"
    # Signature changed: removed argument 'b'
    mutated_code = """
def test_function(a):
    return a
"""

    mock_dependencies = [
        {"name": "caller_a", "file_path": "caller_a.py", "content": "test_function(1, 2)"}
    ]

    with patch.object(
        SafetyVerifier, "_get_downstream_dependencies", return_value=mock_dependencies
    ):
        mock_audit_json = """
{
    "safety_score": 20,
    "risks": ["Signature change: removed argument 'b' used by caller_a"],
    "recommendation": "abort"
}
"""
        with patch(
            "knowledge_os.app.safety_verifier.run_smart_agent_async", return_value=mock_audit_json
        ):
            report = await verifier.verify_mutation(module_name, function_name, mutated_code)

            assert report["safety_score"] == 20
            assert report["recommendation"] == "abort"
            assert "Signature change" in report["risks"][0]


def test_extract_function_args():
    verifier = SafetyVerifier()
    code = """
def my_func(x, y, z=10):
    pass
"""
    args = verifier._extract_function_args(code, "my_func")
    assert args == ["x", "y", "z"]

    # Test with class method
    code_class = """
class MyClass:
    def my_method(self, data):
        pass
"""
    args = verifier._extract_function_args(code_class, "my_method")
    assert args == ["self", "data"]
