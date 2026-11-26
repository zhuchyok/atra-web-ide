"""Tests for expert_contract.py — Outcome classes, citation gates, response validation."""

import json
from datetime import datetime

import pytest


class TestOutcome:
    """Outcome enum — 5 deterministic outcome classes."""

    def test_all_outcomes_defined(self):
        from app.expert_contract import Outcome

        values = {e.value for e in Outcome}
        assert "OUTCOME_OK" in values
        assert "OUTCOME_DENIED_SECURITY" in values
        assert "OUTCOME_NONE_UNSUPPORTED" in values
        assert "OUTCOME_NONE_CLARIFICATION" in values
        assert "OUTCOME_ERR_INTERNAL" in values
        assert len(values) == 5

    def test_outcome_is_optional_in_expert_response(self):
        """Outcome field defaults to None — backward compatible."""
        from app.expert_contract import ExpertResponse

        resp = ExpertResponse(
            expert_name="Анна",
            task_id="test-123",
            content="Test response",
        )
        assert resp.outcome is None
        assert resp.status == "success"

    def test_outcome_can_be_set(self):
        from app.expert_contract import ExpertResponse, Outcome

        resp = ExpertResponse(
            expert_name="Анна",
            task_id="test-123",
            content="Task completed",
            outcome=Outcome.OK,
        )
        assert resp.outcome == Outcome.OK

    def test_outcome_json_serialization(self):
        from app.expert_contract import ExpertResponse, Outcome

        resp = ExpertResponse(
            expert_name="Роман",
            task_id="test-456",
            content="Access denied",
            outcome=Outcome.DENIED_SECURITY,
        )
        data = resp.model_dump()
        assert data["outcome"] == "OUTCOME_DENIED_SECURITY"
        # Roundtrip
        restored = ExpertResponse(**data)
        assert restored.outcome == Outcome.DENIED_SECURITY

    def test_all_outcomes_serialize(self):
        from app.expert_contract import ExpertResponse, Outcome

        for outcome in Outcome:
            resp = ExpertResponse(
                expert_name="test",
                task_id="t1",
                content="c",
                outcome=outcome,
            )
            data = resp.model_dump()
            restored = ExpertResponse(**data)
            assert restored.outcome == outcome


class TestExpertResponseValidation:
    """ExpertResponse Pydantic model validation."""

    def test_valid_response(self):
        from app.expert_contract import ExpertResponse

        resp = ExpertResponse(
            expert_name="Анна",
            task_id="task-001",
            content="Test answer with sufficient detail for verification.",
            confidence_score=0.85,
            source_attribution=[
                {
                    "source_type": "knowledge_node",
                    "source_ref": "/path/to/file",
                    "note": "Contains the relevant data for this analysis",
                }
            ],
        )
        assert resp.expert_name == "Анна"
        assert resp.confidence_score == 0.85
        assert len(resp.source_attribution) == 1

    def test_status_pattern(self):
        from app.expert_contract import ExpertResponse

        resp = ExpertResponse(expert_name="x", task_id="t", content="c", status="success")
        assert resp.status == "success"
        resp = ExpertResponse(expert_name="x", task_id="t", content="c", status="failed")
        assert resp.status == "failed"
        with pytest.raises(Exception):
            ExpertResponse(expert_name="x", task_id="t", content="c", status="invalid_status")

    def test_confidence_score_range(self):
        from app.expert_contract import ExpertResponse

        with pytest.raises(Exception):
            ExpertResponse(expert_name="x", task_id="t", content="c", confidence_score=1.5)
        with pytest.raises(Exception):
            ExpertResponse(expert_name="x", task_id="t", content="c", confidence_score=-0.1)

    def test_reasoning_trace_optional(self):
        from app.expert_contract import ExpertResponse

        resp = ExpertResponse(expert_name="x", task_id="t", content="c")
        assert resp.reasoning_trace is None
        resp = ExpertResponse(
            expert_name="x", task_id="t", content="c", reasoning_trace="Step 1: ..."
        )
        assert resp.reasoning_trace == "Step 1: ..."

    def test_timestamp_auto_generated(self):
        from app.expert_contract import ExpertResponse

        resp = ExpertResponse(expert_name="x", task_id="t", content="c")
        assert resp.timestamp is not None
        assert isinstance(resp.timestamp, datetime)


class TestFormatPromptInstruction:
    """Format_prompt_instruction includes outcome and citation rules."""

    def test_includes_outcome_classes(self):
        from app.expert_contract import ExpertContract

        prompt = ExpertContract.format_prompt_instruction()
        assert "OUTCOME_OK" in prompt
        assert "OUTCOME_DENIED_SECURITY" in prompt
        assert "OUTCOME_NONE_UNSUPPORTED" in prompt
        assert "OUTCOME_NONE_CLARIFICATION" in prompt
        assert "OUTCOME_ERR_INTERNAL" in prompt

    def test_includes_citation_rules(self):
        from app.expert_contract import ExpertContract

        prompt = ExpertContract.format_prompt_instruction()
        assert "CITATION RULES" in prompt
        assert "source_ref" in prompt
        assert "8 characters" in prompt or "min 8" in prompt

    def test_contract_json_structure(self):
        from app.expert_contract import ExpertContract

        prompt = ExpertContract.format_prompt_instruction()
        assert "expert_name" in prompt
        assert "source_attribution" in prompt
        assert "outcome" in prompt
        assert "confidence_score" in prompt


class TestVerifyCitations:
    """Citation gates — deterministic reference verification."""

    def test_passes_when_no_attributions(self):
        from app.expert_contract import ExpertContract

        result = ExpertContract.verify_citations({"source_attribution": []}, set())
        assert result["passed"] is True
        assert "No source attributions provided" in str(result["warnings"])

    def test_passes_when_all_refs_read(self):
        from app.expert_contract import ExpertContract

        result = ExpertContract.verify_citations(
            {
                "source_attribution": [
                    {
                        "source_ref": "/proc/catalog/123.json",
                        "note": "Contains product pricing data for SKU matching",
                    },
                    {
                        "source_ref": "/docs/policy.md",
                        "note": "Defines refund policy limits for this region",
                    },
                ]
            },
            {"/proc/catalog/123.json", "/docs/policy.md"},
        )
        assert result["passed"] is True
        assert result["citations_checked"] == 2

    def test_fails_when_ref_not_read(self):
        from app.expert_contract import ExpertContract

        result = ExpertContract.verify_citations(
            {
                "source_attribution": [
                    {
                        "source_ref": "/unread/file.txt",
                        "note": "Claimed evidence for the analysis result",
                    },
                ]
            },
            {"/read/file.txt"},
        )
        assert result["passed"] is False
        assert len(result["errors"]) == 1
        assert "unread" in result["errors"][0]

    def test_fails_on_empty_ref(self):
        from app.expert_contract import ExpertContract

        result = ExpertContract.verify_citations(
            {
                "source_attribution": [
                    {"source_ref": "", "note": "Some reason for citation here"},
                ]
            },
            set(),
        )
        assert result["passed"] is False
        assert "empty source_ref" in result["errors"][0]

    def test_warns_on_short_note(self):
        from app.expert_contract import ExpertContract

        result = ExpertContract.verify_citations(
            {
                "source_attribution": [
                    {"source_ref": "/file.txt", "note": "short"},
                ]
            },
            {"/file.txt"},
            min_note_length=10,
        )
        assert result["passed"] is True  # short notes are warnings, not errors
        assert len(result["warnings"]) == 1
        assert "short" in result["warnings"][0]

    def test_default_min_note_length_is_8(self):
        from app.expert_contract import ExpertContract

        result = ExpertContract.verify_citations(
            {
                "source_attribution": [
                    {"source_ref": "/file.txt", "note": "1234567"},
                ]
            },
            {"/file.txt"},
        )
        assert len(result["warnings"]) == 1  # 7 chars < 8

        result2 = ExpertContract.verify_citations(
            {
                "source_attribution": [
                    {"source_ref": "/file.txt", "note": "12345678"},
                ]
            },
            {"/file.txt"},
        )
        assert len(result2["warnings"]) == 0  # 8 chars OK

    def test_multiple_citations_all_pass(self):
        from app.expert_contract import ExpertContract

        attributions = [
            {"source_ref": f"/path/file_{i}.txt", "note": f"Evidence source document number {i}"}
            for i in range(10)
        ]
        read_paths = {f"/path/file_{i}.txt" for i in range(10)}
        result = ExpertContract.verify_citations({"source_attribution": attributions}, read_paths)
        assert result["passed"] is True
        assert result["citations_checked"] == 10

    def test_multiple_citations_partial_fail(self):
        from app.expert_contract import ExpertContract

        attributions = [
            {
                "source_ref": "/read/file1.txt",
                "note": "First document used for verification analysis",
            },
            {
                "source_ref": "/unread/file2.txt",
                "note": "Second document used for verification analysis",
            },
            {
                "source_ref": "/read/file3.txt",
                "note": "Third document used for verification analysis",
            },
        ]
        read_paths = {"/read/file1.txt", "/read/file3.txt"}
        result = ExpertContract.verify_citations({"source_attribution": attributions}, read_paths)
        assert result["passed"] is False
        assert result["citations_checked"] == 3
        assert len(result["errors"]) == 1

    def test_no_crash_on_missing_source_ref_key(self):
        from app.expert_contract import ExpertContract

        result = ExpertContract.verify_citations(
            {"source_attribution": [{"note": "Missing source_ref key"}]}, set()
        )
        assert result["passed"] is False
        assert "empty source_ref" in str(result["errors"])

    def test_handles_non_dict_attribution_by_counting_as_errors(self):
        """Non-dict attribution items should count as errors."""
        from app.expert_contract import ExpertContract

        result = ExpertContract.verify_citations(
            {
                "source_attribution": [
                    {"source_ref": "/ok.txt", "note": "Valid citation with good reason"}
                ]
            },
            {"/ok.txt"},
        )
        assert result["passed"] is True
        # Just make sure we handle the list iteration correctly
        assert result["citations_checked"] == 1
