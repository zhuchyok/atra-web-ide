"""Tests for orchestrator_helpers.py — extracted helpers from enhanced_orchestrator.py."""

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


class TestPhaseFunctions:
    """Verify all phase functions are importable and callable."""

    PHASE_NAMES = [
        "phase_auto_fix_errors",
        "phase_autonomous_migrations",
        "phase_victoria_guarantee",
        "phase_prioritize_tasks",
        "phase_decompose_complex",
        "phase_batch_group",
        "phase_red_team_audit",
        "phase_execution_optimizer",
        "phase_registry_reconcile",
        "phase_scale_down_idle",
        "phase_assign_tasks",
        "phase_rollout_kpi",
        "phase_orchestrator_fallback",
        "phase_rebalance",
        "phase_associative_brain",
        "phase_curiosity_engine",
        "phase_global_scout",
        "phase_auto_link",
        "phase_distillation",
        "phase_self_repair",
        "phase_swarm_war_room",
        "phase_meta_architect",
        "phase_evolution",
        "phase_curiosity_gaps",
        "phase_memory_consolidation",
        "phase_multi_cluster_bridge",
        "phase_global_team_sync",
        "phase_knowledge_archivation",
        "phase_cleanup_tasks",
    ]

    def test_all_phase_functions_importable(self):
        import app.orchestrator_helpers as mod

        for name in self.PHASE_NAMES:
            assert hasattr(mod, name), f"{name} missing from orchestrator_helpers"
            assert callable(getattr(mod, name)), f"{name} is not callable"


class TestCalcPriority:
    def test_urgent_keywords(self):
        from app.orchestrator_helpers import _calc_priority

        result = _calc_priority("срочный баг в проде")
        import asyncio

        result = asyncio.run(result)
        assert result == "urgent"

    def test_high_keywords(self):
        import asyncio

        from app.orchestrator_helpers import _calc_priority

        result = asyncio.run(_calc_priority("важная задача"))
        assert result == "high"

    def test_low_priority(self):
        import asyncio

        from app.orchestrator_helpers import _calc_priority

        result = asyncio.run(_calc_priority("обычная задача"))
        assert result is None
