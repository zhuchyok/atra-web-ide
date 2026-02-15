"""
Unit tests for Hierarchical Orchestration (декомпозиция целей, страховки без LLM).
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.hierarchical_orchestration import (
    HierarchicalOrchestrator,
    HierarchicalGoal,
)


@pytest.mark.asyncio
async def test_decompose_goals_fallback_heuristic():
    """При пустом ответе LLM fallback — эвристика по тексту (« и », « затем », запятые)."""
    orch = HierarchicalOrchestrator(root_agent="Виктория")
    with patch.object(orch, "_generate_response", new_callable=AsyncMock, return_value=""):
        goals = await orch._decompose_goals("сделай отчёт и отправь письмо")
    assert len(goals) >= 2
    root = next((g for g in goals if g.level == 0), None)
    assert root is not None
    assert "отчёт" in root.description or "письмо" in root.description
    level1 = [g for g in goals if g.level == 1]
    assert len(level1) >= 1
    # Тексты целей из намерения, не «Подзадача 1»
    descs = [g.description for g in level1]
    assert any("отчёт" in d or "письмо" in d or "отправь" in d for d in descs)


@pytest.mark.asyncio
async def test_decompose_goals_fallback_simple_list():
    """При ответе LLM в формате 1. 2. 3. парсим в root + level-1 цели."""
    orch = HierarchicalOrchestrator(root_agent="Виктория")
    # Первый вызов — пустой (полный формат не распарсился), второй — упрощённый список
    with patch.object(orch, "_generate_response", new_callable=AsyncMock) as m:
        m.side_effect = ["", "1. Подготовить данные\n2. Построить график\n3. Сохранить отчёт"]
        goals = await orch._decompose_goals("построй отчёт")
    assert len(goals) >= 2
    level1 = [g for g in goals if g.level == 1]
    assert len(level1) >= 2
    assert any("данн" in g.description.lower() or "Подготовить" in g.description for g in level1)
    assert any("график" in g.description.lower() or "Построить" in g.description for g in level1)


@pytest.mark.asyncio
async def test_parse_hierarchical_goals_from_response():
    """Парсинг нумерованного списка 0. / 1.1. / 1.1.1."""
    orch = HierarchicalOrchestrator()
    text = """
0. Главная цель
1.1. Цель отдела A
1.1.1. Задача эксперта 1
1.2. Цель отдела B
"""
    parsed = orch._parse_hierarchical_goals_from_response(text, "Главная цель")
    assert parsed is not None
    assert len(parsed) >= 3
    root = next((g for g in parsed if g.level == 0), None)
    assert root is not None
    assert "Главная" in root.description
