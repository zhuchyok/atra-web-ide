"""
Тесты IntegrationBridge: process_task возвращает orchestrator, status, assignments.
use_v2=False или отсутствие V2 → existing. Связь с docs/TESTING_FULL_SYSTEM.md.
Запуск: из knowledge_os: python3 -m pytest tests/test_integration_bridge.py -v
"""
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

os.environ.setdefault("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

import pytest


@pytest.mark.asyncio
async def test_process_task_use_v2_false_returns_existing_format():
    """При use_v2=False возвращается dict с orchestrator=existing, status, assignments."""
    from app.task_orchestration.integration_bridge import IntegrationBridge

    bridge = IntegrationBridge(use_new_orchestration=False)
    result = await bridge.process_task(
        "напиши функцию на Python",
        metadata={},
        use_v2=False,
    )
    assert isinstance(result, dict)
    assert result.get("orchestrator") == "existing"
    assert "status" in result
    assert "assignments" in result
    assert isinstance(result["assignments"], dict)


@pytest.mark.asyncio
async def test_process_task_existing_has_ready_status():
    """Существующий оркестратор возвращает status ready_for_smart_worker или аналог."""
    from app.task_orchestration.integration_bridge import IntegrationBridge

    bridge = IntegrationBridge(use_new_orchestration=False)
    result = await bridge.process_task("проверь код", use_v2=False)
    assert result["orchestrator"] == "existing"
    assert result.get("status") == "ready_for_smart_worker"
