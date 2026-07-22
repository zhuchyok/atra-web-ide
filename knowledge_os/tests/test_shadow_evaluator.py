import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_os.app.shadow_evaluator import ShadowEvaluator


@pytest.mark.asyncio
async def test_compare_responses_win():
    """Проверка логики сравнения (Win)."""
    evaluator = ShadowEvaluator()

    # Мокаем LocalAIRouter
    mock_router = AsyncMock()
    mock_router.run_local_llm.return_value = (
        '{"verdict": "Win", "reasoning": "Shadow is better", "winner": "Shadow"}',
        "ollama",
    )
    evaluator.router = mock_router

    result = await evaluator.compare_responses(
        "How to use async in Python?", "Use asyncio.", "Use asyncio.run() for entry point."
    )

    assert result["verdict"] == "Win"
    assert result["winner"] == "Shadow"
    mock_router.run_local_llm.assert_called_once()


@pytest.mark.asyncio
async def test_compare_responses_invalid_json():
    """Проверка обработки невалидного JSON от судьи."""
    evaluator = ShadowEvaluator()

    mock_router = AsyncMock()
    mock_router.run_local_llm.return_value = ("This is not JSON", "ollama")
    evaluator.router = mock_router

    result = await evaluator.compare_responses("query", "prod", "shadow" * 20)

    # Invalid judge JSON falls back to heuristic (no silent fake Draw-only path)
    assert result["verdict"] in ("Win", "Loss", "Draw")
    assert "heuristic" in result["reasoning"].lower() or "json" in result["reasoning"].lower()


@pytest.mark.asyncio
async def test_update_mutation_stats():
    """Проверка обновления БД (через мок пула)."""
    evaluator = ShadowEvaluator()

    # Мокаем пул соединений
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    evaluator._pool = mock_pool

    await evaluator.update_mutation_stats("mut-123", "Win")

    # Проверяем, что запрос к БД был выполнен
    mock_conn.execute.assert_called_once()
    args = mock_conn.execute.call_args[0][0]
    assert "UPDATE expert_mutations" in args
    assert "win_count = win_count + 1" in args
    assert "id = $1" in args


@pytest.mark.asyncio
async def test_evaluate_and_update_full_cycle():
    """Проверка полного цикла (сравнение + обновление)."""
    evaluator = ShadowEvaluator()

    # Мокаем всё
    mock_router = AsyncMock()
    mock_router.run_local_llm.return_value = (
        '{"verdict": "Loss", "reasoning": "Prod is better", "winner": "Production"}',
        "ollama",
    )
    evaluator.router = mock_router

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    evaluator._pool = mock_pool

    result = await evaluator.evaluate_and_update("mut-456", "query", "prod", "shadow")

    assert result["verdict"] == "Loss"
    assert mock_conn.execute.call_count == 2
    update_sql = mock_conn.execute.call_args_list[0][0][0]
    insert_sql = mock_conn.execute.call_args_list[1][0][0]
    assert "loss_count = loss_count + 1" in update_sql
    assert "INSERT INTO interaction_logs" in insert_sql
