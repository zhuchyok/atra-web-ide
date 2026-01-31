"""
Тесты всей цепочки: просьба → Department Heads → Veronica промпт → распределение → сотрудники → сбор → Victoria синтез.
Проверяем, что цепочка не рвётся и возвращает результат (с моками LLM/БД).
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

os.environ.setdefault("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False


# Минимальная структура организации для тестов
MINIMAL_ORG_STRUCTURE = {
    "departments": [
        {"id": "Strategy/Data", "name": "Strategy/Data", "manager": {"id": 1, "name": "Максим"}, "employees": [], "employee_count": 1}
    ],
    "total_departments": 1,
    "total_employees": 1,
}


@pytest.mark.asyncio
async def test_chain_should_use_department_heads_returns_true_for_request_goal():
    """
    Цепочка шаг 1: для просьбы «Помоги с анализом данных» determine_department
    возвращает Strategy/Data (реальная логика без моков).
    """
    from app.department_heads_system import get_department_heads_system

    db_url = os.getenv("DATABASE_URL")
    system = get_department_heads_system(db_url)
    department = system.determine_department("Помоги с анализом данных")

    assert department == "Strategy/Data", "Просьба без ключевых слов должна дать отдел Strategy/Data"


@pytest.mark.asyncio
async def test_chain_execute_with_task_distribution_returns_result():
    """
    Цепочка шаги 2–6: _execute_with_task_distribution с моком task_dist и _synthesize
    возвращает результат (распределение → выполнение → проверка → сбор отдела → синтез Victoria).
    """
    from app.victoria_enhanced import VictoriaEnhanced
    from app.task_distribution_system import TaskAssignment, TaskStatus, TaskCollection

    goal = "Помоги с анализом данных"
    veronica_prompt = "Задача: анализ. Сотрудник: Максим."
    department = "Strategy/Data"

    # Один выполненный и проверенный assignment
    assignment = TaskAssignment(
        task_id="task_test_1",
        subtask="анализ данных",
        employee_name="Максим",
        department=department,
        status=TaskStatus.COMPLETED,
        result="Результат анализа от Максима",
    )
    assignment_reviewed = TaskAssignment(
        task_id=assignment.task_id,
        subtask=assignment.subtask,
        employee_name=assignment.employee_name,
        department=assignment.department,
        status=TaskStatus.REVIEWED,
        result=assignment.result,
    )
    collection = TaskCollection(
        department=department,
        aggregated_result="Результат анализа от Максима",
        assignments=[assignment_reviewed],
        quality_score=1.0,
    )

    mock_task_dist = MagicMock()
    mock_task_dist.distribute_tasks_from_plan = AsyncMock(return_value=[assignment])  # при task_plan_struct
    mock_task_dist.distribute_tasks_from_veronica_prompt = AsyncMock(return_value=[assignment])
    mock_task_dist.execute_task_assignment = AsyncMock(return_value=assignment)
    mock_task_dist.manager_review_task = AsyncMock(return_value=assignment_reviewed)
    mock_task_dist.department_head_collect_tasks = AsyncMock(return_value=collection)

    with patch("app.task_distribution_system.get_task_distribution_system", return_value=mock_task_dist):
        with patch.object(VictoriaEnhanced, "_synthesize_collected_results", new_callable=AsyncMock, return_value="Итог синтеза по анализу данных"):
            v = VictoriaEnhanced()
            result = await v._execute_with_task_distribution(
                goal, veronica_prompt, MINIMAL_ORG_STRUCTURE, department
            )

    assert result is not None
    assert result.get("method") == "task_distribution"
    assert result.get("result") == "Итог синтеза по анализу данных"
    assert result.get("department") == department
    mock_task_dist.distribute_tasks_from_veronica_prompt.assert_called_once()
    mock_task_dist.execute_task_assignment.assert_called()
    mock_task_dist.manager_review_task.assert_called()
    mock_task_dist.department_head_collect_tasks.assert_called_once()


@pytest.mark.asyncio
async def test_chain_full_solve_returns_result_with_mocks():
    """
    Вся цепочка: solve() с моком _should_use_department_heads и task_dist возвращает результат
    (Department Heads → task distribution → синтез).
    """
    from app.victoria_enhanced import VictoriaEnhanced
    from app.task_distribution_system import TaskAssignment, TaskStatus, TaskCollection

    goal = "Помоги с анализом данных"
    fake_prompt = "ЗАДАЧА: анализ данных. Сотрудник: Максим."
    department = "Strategy/Data"

    coordination_result = {
        "department": department,
        "veronica_prompt": fake_prompt,
        "organizational_structure": MINIMAL_ORG_STRUCTURE,
    }

    assignment = TaskAssignment(
        task_id="task_chain_1",
        subtask="анализ данных",
        employee_name="Максим",
        department=department,
        status=TaskStatus.COMPLETED,
        result="Результат анализа",
    )
    assignment_reviewed = TaskAssignment(
        task_id=assignment.task_id,
        subtask=assignment.subtask,
        employee_name=assignment.employee_name,
        department=assignment.department,
        status=TaskStatus.REVIEWED,
        result=assignment.result,
    )
    collection = TaskCollection(
        department=department,
        aggregated_result="Результат анализа",
        assignments=[assignment_reviewed],
        quality_score=1.0,
    )

    mock_task_dist = MagicMock()
    mock_task_dist.distribute_tasks_from_plan = AsyncMock(return_value=[assignment])
    mock_task_dist.distribute_tasks_from_veronica_prompt = AsyncMock(return_value=[assignment])
    mock_task_dist.execute_task_assignment = AsyncMock(return_value=assignment)
    mock_task_dist.manager_review_task = AsyncMock(return_value=assignment_reviewed)
    mock_task_dist.department_head_collect_tasks = AsyncMock(return_value=collection)

    async def mock_should_use(goal_arg, category=None):
        return True, coordination_result

    with patch.object(VictoriaEnhanced, "_should_use_department_heads", side_effect=mock_should_use):
        with patch("app.task_distribution_system.get_task_distribution_system", return_value=mock_task_dist):
            with patch.object(VictoriaEnhanced, "_synthesize_collected_results", new_callable=AsyncMock, return_value="Финальный итог по анализу данных"):
                v = VictoriaEnhanced()
                result = await v.solve(goal)

    assert result is not None, "solve() должен вернуть результат"
    assert "result" in result
    assert result.get("method") in ("task_distribution", "department_heads")
    assert "Финальный итог" in (result.get("result") or "")


def run_all_without_pytest():
    """Запуск без pytest."""
    async def _run():
        await test_chain_should_use_department_heads_returns_true_for_request_goal()
        print("✅ test_chain_should_use_department_heads_returns_true_for_request_goal")
        await test_chain_execute_with_task_distribution_returns_result()
        print("✅ test_chain_execute_with_task_distribution_returns_result")
        await test_chain_full_solve_returns_result_with_mocks()
        print("✅ test_chain_full_solve_returns_result_with_mocks")
        print("\n✅ Вся цепочка (с моками) работает.")

    asyncio.run(_run())


if __name__ == "__main__":
    run_all_without_pytest()
