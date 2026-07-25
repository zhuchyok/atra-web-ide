"""Tests for strategic_board.py — Board of Directors autopilot."""

import json

import pytest
from app.strategic_board import (
    directive_matches_question_intent,
    extract_question_intent_terms,
    is_low_quality_directive,
    parse_directive_structure,
)


class TestIntentFidelity:
    def test_extracts_content_terms(self):
        terms = extract_question_intent_terms(
            "Нужно ли разгружать тяжёлые модели Ollama перед заседанием Совета?"
        )
        assert "разгружать" in terms or "ollama" in terms
        assert "нужно" not in terms

    def test_rejects_okr_drift_away_from_unload_question(self):
        q = "Нужно ли разгружать тяжёлые модели Ollama перед заседанием Совета?"
        drift = """РЕШЕНИЕ: Начать внедрение моделей Ollama в производственную среду
ОБОСНОВАНИЕ: Это повысит технологический суверенитет и интеллектуальный капитал.
РИСКИ: Сложность интеграции
УВЕРЕННОСТЬ: 0.7"""
        assert directive_matches_question_intent(q, drift) is False

    def test_rejects_wrong_polarity_mass_reset(self):
        q = "Стоит ли сейчас массово reset failed tasks по timeout, или оставить как историю?"
        bad = """РЕШЕНИЕ: Решить массово timeout failed tasks
ОБОСНОВАНИЕ: Сброс простоящих задач повысит эффективность.
РИСКИ: Потеря контекста
УВЕРЕННОСТЬ: 0.6"""
        assert directive_matches_question_intent(q, bad) is False

    def test_accepts_leave_failed_as_history(self):
        q = "Стоит ли сейчас массово reset failed tasks по timeout, или оставить как историю?"
        good = """РЕШЕНИЕ: Не делать массовый reset — оставить failed timeout как историю и разобрать точечно
ОБОСНОВАНИЕ: Массовый сброс вернёт шум в очередь; точечный анализ безопаснее.
РИСКИ: Часть задач останется failed до ручного разбора
УВЕРЕННОСТЬ: 0.85"""
        assert directive_matches_question_intent(q, good) is True

    def test_accepts_intent_aligned_unload_answer(self):
        q = "Нужно ли разгружать тяжёлые модели Ollama перед заседанием Совета?"
        good = """РЕШЕНИЕ: Да — выгрузить тяжёлые модели Ollama перед заседанием Совета
ОБОСНОВАНИЕ: Разгрузка освобождает память и снижает конкуренцию, директивы становятся точнее.
РИСКИ: Кратковременная задержка codegen
УВЕРЕННОСТЬ: 0.88"""
        assert directive_matches_question_intent(q, good) is True

    def test_nightly_short_question_skips_gate(self):
        assert directive_matches_question_intent("Daily Strategic Board Meeting", "x") is True


class TestLowQualityDirective:
    def test_rejects_placeholder_template(self):
        text = """РЕШЕНИЕ: [одна фраза]
ОБОСНОВАНИЕ: [2-3 предложения]
РИСКИ: [кратко]
УВЕРЕННОСТЬ: [0.0-1.0]"""
        assert is_low_quality_directive(text) is True

    def test_rejects_example_n_of_prompt_echo(self):
        text = """Пример 2 из 3 предложений (работает ли совет директоров):

РЕШЕНИЕ: [одна фраза]
ОБОСНОВАНИЕ: [2-3 предложения]
РИСКИ: [кратко]
УВЕРЕННОСТЬ: [0.0-1.0]"""
        assert is_low_quality_directive(text) is True

    def test_accepts_substantive_directive(self):
        text = """РЕШЕНИЕ: Удержать offline-first контур и разгрузить Ollama перед board consult
ОБОСНОВАНИЕ: При конкуренции тяжёлых моделей директивы деградируют до шаблонов.
РИСКИ: Кратковременное снижение codegen throughput; задержка nightly meeting.
УВЕРЕННОСТЬ: 0.86"""
        assert is_low_quality_directive(text) is False

    def test_rejects_template_action_placeholders(self):
        text = """ДЕЙСТВИЯ:
1) первое действие
2) второе действие
3) третье действие

РЕШЕНИЕ: Приоритизировать завершение backlog Knowledge OS
ОБОСНОВАНИЕ: Нужен фокус на стабильности.
РИСКИ: Задержка фич.
УВЕРЕННОСТЬ: 0.7"""
        assert is_low_quality_directive(text) is True


class TestParseDirectiveStructure:
    """Test parsing of board directive text into structured decisions."""

    def test_parse_full_directive(self):
        text = """РЕШЕНИЕ: Улучшить стабильность системы
ОБОСНОВАНИЕ: Участились сбои в работе экспертов
РИСКИ: Возможна временная деградация скорости
УВЕРЕННОСТЬ: 0.85"""
        result = parse_directive_structure(text)
        assert result["decision"] == "Улучшить стабильность системы"
        assert len(result["action_items"]) == 0  # base version without focuses parser
        assert result["confidence"] == 0.85
        assert result.get("recommend_human_review") is False

    def test_parse_minimal_directive(self):
        text = """РЕШЕНИЕ: Тест
ОБОСНОВАНИЕ: Просто проверка"""
        result = parse_directive_structure(text)
        assert result["decision"] == "Тест"
        assert result["confidence"] == 0.8
        assert result.get("recommend_human_review") is False
        assert result["action_items"] == []

    def test_parse_with_human_review(self):
        text = """РЕШЕНИЕ: Критическое изменение
ОБОСНОВАНИЕ: Высокий риск
УВЕРЕННОСТЬ: 0.65
ТРЕБУЕТ ПОДТВЕРЖДЕНИЯ ЧЕЛОВЕКОМ"""
        result = parse_directive_structure(text)
        assert result.get("recommend_human_review") is True
        assert result["confidence"] == 0.65

    def test_parse_empty_text(self):
        result = parse_directive_structure("")
        assert result["decision"] == ""
        assert result["confidence"] == 0.8

    def test_parse_english_keywords(self):
        text = """DECISION: Upgrade infrastructure
RATIONALE: Performance issues
CONFIDENCE: 0.9
FOCUSES:
- Improve MLX throughput
- Add monitoring
RISKS: Downtime during migration"""
        result = parse_directive_structure(text)
        assert "Upgrade" in result["decision"]
        assert result["confidence"] == 0.9

    def test_parse_with_risks(self):
        text = """РЕШЕНИЕ: Обновить БД
ОБОСНОВАНИЕ: Безопасность
РИСКИ:
- Потеря данных
- Долгий миграция
- Откат сложный
УВЕРЕННОСТЬ: 0.75"""
        result = parse_directive_structure(text)
        assert len(result["risks"]) >= 2

    def test_parse_radical_decision(self):
        text = """РЕШЕНИЕ: Рефакторинг
ОБОСНОВАНИЕ: Техдолг
УВЕРЕННОСТЬ: 0.88"""
        result = parse_directive_structure(text)
        assert result["confidence"] == 0.88

    def test_parse_confidence_lower_bound(self):
        text = """РЕШЕНИЕ: Бюджетное
ОБОСНОВАНИЕ: Экономия
УВЕРЕННОСТЬ: 0.10"""
        result = parse_directive_structure(text)
        assert result["confidence"] == 0.1
