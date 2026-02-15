"""
Тесты маршрутизации задач Victoria: task_detector (тип задачи, use_enhanced).
Связь с docs/VICTORIA_TASK_CHAIN_FULL.md и VERONICA_REAL_ROLE: при PREFER_EXPERTS_FIRST
простые одношаговые (покажи файлы) → veronica; «напиши/сделай» → enhanced.
Запуск: pytest backend/app/tests/test_task_detector_chain.py -v
"""
import os
import sys
from pathlib import Path

# Корень репозитория для импорта src.agents.bridge (backend/app/tests -> parents[3] = repo root)
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from src.agents.bridge.task_detector import detect_task_type, should_use_enhanced, is_curator_standard_goal


@pytest.fixture(autouse=True)
def prefer_experts_first():
    """По умолчанию PREFER_EXPERTS_FIRST=true (документированное поведение)."""
    old = os.environ.get("PREFER_EXPERTS_FIRST")
    os.environ["PREFER_EXPERTS_FIRST"] = "true"
    yield
    if old is not None:
        os.environ["PREFER_EXPERTS_FIRST"] = old
    elif "PREFER_EXPERTS_FIRST" in os.environ:
        del os.environ["PREFER_EXPERTS_FIRST"]


class TestDetectTaskType:
    """Тип задачи для маршрутизации: simple_chat, veronica, department_heads, enhanced."""

    def test_simple_chat(self):
        assert detect_task_type("привет", "") == "simple_chat"
        assert detect_task_type("здравствуй, как дела?", "") == "simple_chat"
        assert detect_task_type("кто ты", "") == "simple_chat"

    def test_veronica_simple_list(self):
        """Одношаговые запросы (руки) → Veronica."""
        assert detect_task_type("покажи файлы в frontend", "") == "veronica"
        assert detect_task_type("покажи список файлов в корне проекта", "") == "veronica"
        assert detect_task_type("выведи список файлов", "") == "veronica"

    def test_enhanced_execution(self):
        """«Напиши/сделай» при PREFER_EXPERTS_FIRST → enhanced (эксперты первыми)."""
        assert detect_task_type("напиши функцию сортировки", "") == "enhanced"
        assert detect_task_type("сделай проверку кода", "") == "enhanced"
        assert detect_task_type("напиши одну строку кода на Python", "") == "enhanced"

    def test_department_heads(self):
        """Аналитика/стратегия → department_heads."""
        assert detect_task_type("проанализируй данные продаж", "") == "department_heads"
        assert detect_task_type("разработай стратегию", "") == "department_heads"

    def test_enhanced_general(self):
        """Архитектура/общие сложные → enhanced."""
        assert detect_task_type("разработай архитектуру системы", "") == "enhanced"

    def test_curator_standard_go_to_enhanced(self):
        """Кураторские эталоны (статус проекта, что умеешь, дашборд) → enhanced, не Veronica."""
        assert detect_task_type("какой статус проекта?", "") == "enhanced"
        assert detect_task_type("что ты умеешь?", "") == "enhanced"
        assert detect_task_type("статус по проекту", "") == "enhanced"
        assert detect_task_type("где дашборд?", "") == "enhanced"

    def test_empty_goal(self):
        assert detect_task_type("", "") == "simple_chat"
        assert detect_task_type("   ", "") == "simple_chat"


class TestShouldUseEnhanced:
    """should_use_enhanced: False для simple_chat, иначе по use_enhanced_env."""

    def test_simple_chat_no_enhanced(self):
        """Приветствия не тянут Enhanced даже если env=true."""
        assert should_use_enhanced("привет", None, True) is False
        assert should_use_enhanced("кто ты", "", True) is False

    def test_veronica_goal_use_enhanced(self):
        """Покажи файлы — use_enhanced может быть True (маршрут всё равно veronica по типу)."""
        # use_enhanced=True в env → для не-simple_chat возвращаем True
        assert should_use_enhanced("покажи список файлов", None, True) is True

    def test_enhanced_goal_use_enhanced(self):
        assert should_use_enhanced("напиши код", None, True) is True

    def test_env_false(self):
        """Если use_enhanced_env=False — всегда False."""
        assert should_use_enhanced("напиши код", None, False) is False

    def test_curator_standard_use_enhanced(self):
        """Кураторские запросы идут в Enhanced (RAG/эталоны)."""
        assert should_use_enhanced("какой статус проекта?", None, True) is True
        assert should_use_enhanced("что ты умеешь?", None, True) is True


class TestIsCuratorStandardGoal:
    """is_curator_standard_goal: цели куратора не делегировать в Veronica."""

    def test_curator_standard_true(self):
        assert is_curator_standard_goal("какой статус проекта?") is True
        assert is_curator_standard_goal("статус проекта") is True
        assert is_curator_standard_goal("что умеешь?") is True
        assert is_curator_standard_goal("где дашборд") is True

    def test_curator_standard_false(self):
        assert is_curator_standard_goal("привет") is False
        assert is_curator_standard_goal("покажи файлы") is False
        assert is_curator_standard_goal("напиши код") is False
        assert is_curator_standard_goal("") is False


class TestOrchestrationContext:
    """Логика цепочки: план оркестратора → текст контекста для Victoria. Тесты без поднятия сервера."""

    @pytest.fixture
    def build_and_recommends(self):
        try:
            from src.agents.bridge.victoria_server import (
                _build_orchestration_context,
                _orchestrator_recommends_veronica,
            )
            return _build_orchestration_context, _orchestrator_recommends_veronica
        except Exception as e:
            pytest.skip(f"victoria_server не импортируется (нужны deps): {e}")

    def test_build_context_empty(self, build_and_recommends):
        build_ctx, _ = build_and_recommends
        assert build_ctx(None) == ""
        assert build_ctx({}) == ""
        assert build_ctx({"assignments": {}, "strategy": None}) == ""

    def test_build_context_with_strategy(self, build_and_recommends):
        build_ctx, _ = build_and_recommends
        out = build_ctx({"strategy": "Сначала анализ, затем код"})
        assert "План от оркестратора" in out
        assert "Стратегия оркестратора" in out
        assert "Сначала анализ" in out

    def test_build_context_with_assignments(self, build_and_recommends):
        build_ctx, _ = build_and_recommends
        out = build_ctx({
            "assignments": {"main": {"expert_name": "Игорь", "expert_id": "igor"}},
        })
        assert "План от оркестратора" in out
        assert "Назначения" in out
        assert "Игорь" in out

    def test_build_context_with_strategy_and_assignments(self, build_and_recommends):
        """Контекст содержит и стратегию, и назначения — оба используются в цепочке."""
        build_ctx, _ = build_and_recommends
        out = build_ctx({
            "strategy": "Сначала анализ кода, затем рефакторинг",
            "assignments": {"main": {"expert_name": "Анна", "expert_id": "anna"}},
        })
        assert "План от оркестратора" in out
        assert "Стратегия оркестратора" in out
        assert "Сначала анализ" in out
        assert "Назначения" in out
        assert "Анна" in out

    def test_orchestrator_recommends_veronica_false(self, build_and_recommends):
        _, recommends = build_and_recommends
        assert recommends(None) is False
        assert recommends({}) is False
        assert recommends({"assignments": {"main": {"expert_name": "Игорь"}}}) is False

    def test_orchestrator_recommends_veronica_true(self, build_and_recommends):
        _, recommends = build_and_recommends
        assert recommends({"assignments": {"main": {"expert_name": "Veronica"}}}) is True
        assert recommends({"assignments": {"main": {"expert_name": "Вероника"}}}) is True
