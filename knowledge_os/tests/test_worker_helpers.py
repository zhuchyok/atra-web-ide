"""Tests for worker_helpers.py — extracted helpers from expert_worker.py."""

import pytest


class TestBuildContractTrace:
    def test_returns_defaults_for_empty(self):
        from app.worker_helpers import build_contract_trace

        result = build_contract_trace({})
        assert result["version"] == "1"
        assert result["intent"] == "execute_assigned_task"
        assert result["risk_level"] == "medium"
        assert result["audit_required"] is False

    def test_uses_provided_values(self):
        from app.worker_helpers import build_contract_trace

        contract = {"version": "2", "intent": "audit", "risk_level": "high", "audit_required": True}
        result = build_contract_trace(contract)
        assert result["version"] == "2"
        assert result["intent"] == "audit"
        assert result["risk_level"] == "high"
        assert result["audit_required"] is True

    def test_handles_non_dict(self):
        from app.worker_helpers import build_contract_trace

        result = build_contract_trace(None)
        assert result["version"] == "1"


class TestExtractSourceAttribution:
    def test_returns_empty_for_empty_metadata(self):
        from app.worker_helpers import extract_source_attribution

        result = extract_source_attribution({})
        assert result == []

    def test_extracts_source_refs_list(self):
        from app.worker_helpers import extract_source_attribution

        md = {
            "source_refs": [
                {"source_type": "paper", "source_ref": "arxiv:1234", "note": "key reference"}
            ]
        }
        result = extract_source_attribution(md)
        assert len(result) == 1
        assert result[0]["source_type"] == "paper"
        assert result[0]["source_ref"] == "arxiv:1234"

    def test_deduplicates(self):
        from app.worker_helpers import extract_source_attribution

        md = {
            "source_refs": [{"source_type": "paper", "source_ref": "same_id"}],
            "citations": [{"source_type": "paper", "source_ref": "same_id"}],
        }
        result = extract_source_attribution(md)
        assert len(result) == 1

    def test_extracts_scalar_sources(self):
        from app.worker_helpers import extract_source_attribution

        md = {"source": "main.py"}
        result = extract_source_attribution(md)
        assert any(s["source_ref"] == "main.py" for s in result)


class TestEligibleForTask:
    def test_no_filters_returns_true(self):
        from app.worker_helpers import eligible_for_task

        task_goal = {"task_id": "test_1", "metadata": {}}
        assert eligible_for_task(task_goal, "Виктория", False, None, None) is True

    def test_target_expert_filter(self):
        from app.worker_helpers import eligible_for_task

        task_goal = {"task_id": "test_1", "metadata": {"target_expert": "Анна"}}
        assert eligible_for_task(task_goal, "Виктория", True, None, None) is False
        assert eligible_for_task(task_goal, "Анна", True, None, None) is True

    def test_verification_experts_filter(self):
        from app.worker_helpers import eligible_for_task

        task_goal = {"task_id": "VERIFY_001", "metadata": {}}
        assert eligible_for_task(task_goal, "Виктория", False, ["Анна"], None) is False
        assert eligible_for_task(task_goal, "Анна", False, ["Анна"], None) is True

    def test_rd_excluded_filter(self):
        from app.worker_helpers import eligible_for_task

        task_goal = {"task_id": "RD_001", "metadata": {}}
        assert eligible_for_task(task_goal, "Виктория", False, None, ["Виктория"]) is False
        assert eligible_for_task(task_goal, "Анна", False, None, ["Виктория"]) is True


class TestNormalizeContract:
    def test_returns_none_for_invalid_type(self):
        from app.worker_helpers import normalize_contract

        payload = {"contract": "not_a_dict"}
        assert normalize_contract(payload, {"1"}) is None

    def test_returns_none_for_unversioned_enforced(self):
        from app.worker_helpers import normalize_contract

        payload = {"contract": {"version": "99"}, "metadata": {"contract_enforce": True}}
        assert normalize_contract(payload, {"1"}) is None

    def test_shadow_mode_pass_through(self):
        from app.worker_helpers import normalize_contract

        payload = {
            "contract": {"version": "99", "intent": "test"},
            "metadata": {"contract_enforce": False},
        }
        result = normalize_contract(payload, {"1"})
        assert result is not None
        assert result["version"] == "99"

    def test_normalizes_correctly(self):
        from app.worker_helpers import normalize_contract

        payload = {
            "contract": {
                "version": "1",
                "intent": "execute",
                "output_schema": "v1",
                "risk_level": "low",
            }
        }
        result = normalize_contract(payload, {"1"})
        assert result["version"] == "1"
        assert result["intent"] == "execute"
        assert result["audit_required"] is False

    def test_defaults_missing_fields(self):
        from app.worker_helpers import normalize_contract

        payload = {"contract": {"version": "1"}}
        result = normalize_contract(payload, {"1"})
        assert result["intent"] == "execute_assigned_task"
        assert result["output_schema"] == "expert_response_v1"
        assert result["risk_level"] == "medium"


class TestPreflightChecks:
    @pytest.mark.asyncio
    async def test_returns_true_on_normal_path(self):
        from app.worker_helpers import preflight_checks

        result = await preflight_checks(
            "test-id",
            "test-expert",
            False,
            False,
            {},
            lambda: None,
            type("obj", (object,), {"get_client": lambda: None})(),
        )
        assert result is True


class TestCalculateAdaptiveTimeout:
    @pytest.mark.asyncio
    async def test_returns_timeout(self):
        from app.worker_helpers import calculate_adaptive_timeout

        task_data = {"metadata": {}, "description": "simple task"}
        timeout, is_dialogue, is_monster = await calculate_adaptive_timeout(
            task_data,
            "simple task",
            "test",
            "task1",
            type("obj", (object,), {"get_client": lambda: None})(),
        )
        assert timeout is not None
        assert isinstance(timeout, float)
        assert is_dialogue is False
        assert is_monster is False

    @pytest.mark.asyncio
    async def test_dialogue_task_shorter_timeout(self):
        from app.worker_helpers import calculate_adaptive_timeout

        task_data = {"metadata": {"is_dialogue": True}}
        timeout, is_dialogue, _ = await calculate_adaptive_timeout(
            task_data,
            "",
            "test",
            "d1",
            type("obj", (object,), {"get_client": lambda: None})(),
        )
        assert is_dialogue is True
        assert timeout == 300.0
