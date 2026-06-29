"""Tests for strategic_board.py — Board of Directors autopilot."""

import json
import pytest
from app.strategic_board import parse_directive_structure


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
