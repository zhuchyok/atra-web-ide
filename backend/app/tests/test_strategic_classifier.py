"""
Тесты классификатора стратегических вопросов (чат → board/consult → Victoria).
VERIFICATION_CHECKLIST §36, PROJECT_GAPS §2: сценарий стратегический вопрос → Совет Директоров.
"""

import pytest

from app.services.strategic_classifier import (
    is_strategic_question,
    get_risk_level_from_question,
)


class TestIsStrategicQuestion:
    """is_strategic_question: True для стратегических, False для обычных."""

    def test_strategic_two_keywords(self):
        is_st, reason = is_strategic_question(
            "Как расставить приоритеты по архитектуре и срокам?"
        )
        assert is_st is True
        assert "strategic" in reason.lower() or "priority" in reason.lower() or "architect" in reason.lower()

    def test_strategic_keyword_with_question(self):
        is_st, reason = is_strategic_question(
            "Стоит ли переходить на микросервисы в нашем проекте?"
        )
        assert is_st is True

    def test_non_strategic_short(self):
        is_st, reason = is_strategic_question("Привет!")
        assert is_st is False
        assert "short" in reason.lower()

    def test_non_strategic_casual(self):
        is_st, _ = is_strategic_question("Как дела? Что умеешь?")
        assert is_st is False

    def test_non_strategic_simple_code(self):
        is_st, _ = is_strategic_question("Как написать функцию для сортировки списка?")
        assert is_st is False

    def test_strategic_phrase_stoit_li(self):
        is_st, _ = is_strategic_question(
            "Стоит ли нам полностью переписать бэкенд на другой фреймворк?"
        )
        assert is_st is True


class TestGetRiskLevel:
    """get_risk_level_from_question: high / medium / low."""

    def test_high_risk_architecture(self):
        assert get_risk_level_from_question("Архитектура и безопасность системы") == "high"

    def test_medium_risk_refactor(self):
        assert get_risk_level_from_question("Рефакторинг и приоритеты по срокам") == "medium"

    def test_low_risk_default(self):
        assert get_risk_level_from_question("Как настроить линтер?") == "low"
