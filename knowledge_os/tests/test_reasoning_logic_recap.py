"""
Фаза 5 плана «Логика мысли»: unit-тесты ReCAP — рефлексия и пересмотр плана.
Проверяем: _is_step_failed_or_empty, _build_high_level_prompt с previous_plan_failure,
_execute_plan возвращает (results, should_replan, failure_info).
Запуск: pytest knowledge_os/tests/test_reasoning_logic_recap.py -v
"""

import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


class TestRecapStepFailedOrEmpty:
    """Чекпоинт рефлексии: шаг считается провальным при пустом/ошибочном результате."""

    def test_none_is_failed(self):
        from app.recap_framework import ReCAPFramework
        fw = ReCAPFramework(reflection_enabled=True, max_plan_revisions=1)
        assert fw._is_step_failed_or_empty(None) is True

    def test_empty_string_is_failed(self):
        from app.recap_framework import ReCAPFramework
        fw = ReCAPFramework(reflection_enabled=True, max_plan_revisions=1)
        assert fw._is_step_failed_or_empty("") is True
        assert fw._is_step_failed_or_empty("   ") is True

    def test_error_keywords_are_failed(self):
        from app.recap_framework import ReCAPFramework
        fw = ReCAPFramework(reflection_enabled=True, max_plan_revisions=1)
        assert fw._is_step_failed_or_empty("ошибка при выполнении") is True
        assert fw._is_step_failed_or_empty("Error: timeout") is True
        assert fw._is_step_failed_or_empty("step failed") is True
        assert fw._is_step_failed_or_empty("не удалось получить данные") is True
        assert fw._is_step_failed_or_empty("exception in code") is True

    def test_non_empty_ok_is_not_failed(self):
        from app.recap_framework import ReCAPFramework
        fw = ReCAPFramework(reflection_enabled=True, max_plan_revisions=1)
        assert fw._is_step_failed_or_empty("Результат: 42") is False
        assert fw._is_step_failed_or_empty("Файл создан") is False
        assert fw._is_step_failed_or_empty("OK") is False


class TestRecapBuildHighLevelPrompt:
    """При пересмотре плана в контексте должен быть блок «ПРЕДЫДУЩАЯ ПОПЫТКА НЕ УДАЛАСЬ»."""

    def test_previous_plan_failure_in_prompt(self):
        from app.recap_framework import ReCAPFramework
        fw = ReCAPFramework(reflection_enabled=True, max_plan_revisions=1)
        context = {
            "previous_plan_failure": {
                "step_description": "Получить данные из API",
                "reason": "таймаут",
            }
        }
        prompt = fw._build_high_level_prompt("Построить отчёт", context)
        assert "ПРЕДЫДУЩАЯ ПОПЫТКА НЕ УДАЛАСЬ" in prompt
        assert "Получить данные" in prompt or "API" in prompt
        assert "таймаут" in prompt

    def test_no_previous_failure_no_block(self):
        from app.recap_framework import ReCAPFramework
        fw = ReCAPFramework(reflection_enabled=True, max_plan_revisions=1)
        prompt = fw._build_high_level_prompt("Построить отчёт", None)
        assert "ПРЕДЫДУЩАЯ ПОПЫТКА" not in prompt

    def test_context_without_previous_failure_no_block(self):
        from app.recap_framework import ReCAPFramework
        fw = ReCAPFramework(reflection_enabled=True, max_plan_revisions=1)
        prompt = fw._build_high_level_prompt("Задача", {"other": "data"})
        assert "ПРЕДЫДУЩАЯ ПОПЫТКА" not in prompt


class TestRecapExecutePlanReturnSignature:
    """_execute_plan возвращает (results, should_replan, failure_info)."""

    @pytest.mark.asyncio
    async def test_execute_plan_returns_tuple_of_three(self):
        from app.recap_framework import ReCAPFramework, ReCAPPlan, PlanStep, PlanningLevel
        fw = ReCAPFramework(reflection_enabled=False)
        plan = ReCAPPlan(
            goal="Test",
            high_level_steps=[
                PlanStep(1, "Step 1", PlanningLevel.HIGH_LEVEL, []),
            ],
            mid_level_steps=[],
            low_level_steps=[],
        )
        results, should_replan, failure_info = await fw._execute_plan(plan, revision_count=0)
        assert isinstance(results, dict)
        assert isinstance(should_replan, bool)
        assert failure_info is None or isinstance(failure_info, dict)
