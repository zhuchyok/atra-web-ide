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
УВЕРЕННОСТЬ: 0.85
ФОКУСЫ:
1) Оптимизировать MLX очередь
2) Добавить мониторинг Redis
3) Обновить конфиги экспертов
РАДИКАЛЬНОЕ РЕШЕНИЕ: Перейти на async обработку"""
        result = parse_directive_structure(text)
        assert result["decision"] == "Улучшить стабильность системы"
        assert len(result["focuses"]) == 3
        assert len(result["action_items"]) == 4
        assert result["confidence"] == 0.85
        assert result.get("recommend_human_review") is False

    def test_parse_minimal_directive(self):
        text = """РЕШЕНИЕ: Тест
ОБОСНОВАНИЕ: Просто проверка"""
        result = parse_directive_structure(text)
        assert result["decision"] == "Тест"
        assert result["confidence"] == 0.8  # default
        assert result.get("recommend_human_review") is False
        assert result["action_items"] == []
        assert result["focuses"] == []

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
УВЕРЕННОСТЬ: 0.88
ФОКУСЫ:
1) Убрать legacy код
РАДИКАЛЬНОЕ РЕШЕНИЕ: Переписать с нуля"""
        result = parse_directive_structure(text)
        assert len(result["action_items"]) == 2
        assert any("РАДИКАЛЬНО" in a["task"] for a in result["action_items"])

    def test_parse_confidence_lower_bound(self):
        text = """РЕШЕНИЕ: Бюджетное
ОБОСНОВАНИЕ: Экономия
УВЕРЕННОСТЬ: 0.10"""
        result = parse_directive_structure(text)
        assert result["confidence"] == 0.1
