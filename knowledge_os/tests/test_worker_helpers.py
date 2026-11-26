"""Tests for worker_helpers.py — helpers that exist in tree."""

from app.worker_helpers import build_contract_trace, extract_source_attribution


class TestBuildContractTrace:
    def test_returns_defaults_for_empty(self):
        result = build_contract_trace({})
        assert result["version"] == "1"
        assert result["intent"] == "execute_assigned_task"
        assert result["risk_level"] == "medium"
        assert result["audit_required"] is False

    def test_uses_provided_values(self):
        contract = {
            "version": "2",
            "intent": "audit",
            "risk_level": "high",
            "audit_required": True,
        }
        result = build_contract_trace(contract)
        assert result["version"] == "2"
        assert result["intent"] == "audit"
        assert result["risk_level"] == "high"
        assert result["audit_required"] is True

    def test_handles_non_dict(self):
        result = build_contract_trace(None)
        assert result["version"] == "1"


class TestExtractSourceAttribution:
    def test_returns_empty_for_empty_metadata(self):
        assert extract_source_attribution({}) == []

    def test_extracts_source_refs_list(self):
        md = {
            "source_refs": [
                {"type": "paper", "ref": "arxiv:1234", "note": "key reference"},
            ]
        }
        result = extract_source_attribution(md)
        assert len(result) == 1
        assert result[0]["source_type"] == "paper"
        assert result[0]["source_ref"] == "arxiv:1234"

    def test_extracts_string_list(self):
        md = {"sources": ["main.py"]}
        result = extract_source_attribution(md)
        assert any(s["source_ref"] == "main.py" for s in result)
