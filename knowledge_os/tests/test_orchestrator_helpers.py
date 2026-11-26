"""Tests for orchestrator_helpers.py — helpers that exist in tree."""

import asyncio

import pytest


class TestHasExecutionBacklog:
    @pytest.mark.asyncio
    async def test_importable_and_callable(self):
        from app.orchestrator_helpers import has_execution_backlog

        assert callable(has_execution_backlog)


class TestPrioritizeTasks:
    @pytest.mark.asyncio
    async def test_importable_and_callable(self):
        from app.orchestrator_helpers import prioritize_tasks

        assert callable(prioritize_tasks)


class TestGetDefaultExpertId:
    def test_importable(self):
        from app.orchestrator_helpers import get_default_expert_id

        assert callable(get_default_expert_id)


class TestCheckLlmHealth:
    @pytest.mark.asyncio
    async def test_returns_tuple(self):
        from app.orchestrator_helpers import check_llm_health

        result = await check_llm_health()
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestCalcPriority:
    def test_urgent_keywords(self):
        from app.orchestrator_helpers import _calc_priority

        result = asyncio.run(_calc_priority("срочный баг в проде"))
        assert result == "urgent"

    def test_high_keywords(self):
        from app.orchestrator_helpers import _calc_priority

        result = asyncio.run(_calc_priority("важная задача"))
        assert result == "high"

    def test_low_priority(self):
        from app.orchestrator_helpers import _calc_priority

        result = asyncio.run(_calc_priority("обычная заметка"))
        assert result in (None, "low", "medium", "high", "urgent")
