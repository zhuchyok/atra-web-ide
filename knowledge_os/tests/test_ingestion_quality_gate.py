import pytest
from app.ingestion.quality_gate import GateDecision, IngestionQualityGate


def test_reject_prompt_artifact():
    gate = IngestionQualityGate()
    result = gate.evaluate(
        "Role: Victoria\nTone: Professional\nStrategy: Concise", source_type="agent"
    )
    assert result.decision == "reject"
    assert result.reason == "prompt_artifact"


def test_accept_clean_knowledge():
    gate = IngestionQualityGate()
    text = (
        "Postgres row-level locking with FOR UPDATE SKIP LOCKED prevents duplicate claims in multi-worker queues. "
        "Use it for deterministic task leasing and combine it with short leases for safe retries."
    )
    result = gate.evaluate(text, source_type="agent")
    assert result.decision in ("accept", "borderline")


@pytest.mark.asyncio
async def test_borderline_invalid_judge_is_rejected():
    class FakeJudge:
        async def evaluate(self, text: str, source_type: str):
            return {"foo": "bar"}

    gate = IngestionQualityGate(judge=FakeJudge())
    decision = await gate.evaluate_async(
        "Итог: решение есть, но шаги описаны неполно и частично смешаны с контекстом.",
        "agent",
    )
    assert isinstance(decision, GateDecision)
    assert decision.decision == "reject"
    assert decision.reason == "judge_invalid"


def test_shadow_mode_never_blocks(monkeypatch):
    monkeypatch.setenv("INGESTION_GATE_SHADOW_MODE", "true")
    monkeypatch.setenv("INGESTION_GATE_ENFORCE_PERCENT", "100")
    gate = IngestionQualityGate()
    decision = GateDecision(decision="reject", reason="prompt_artifact", quality_score=0.0)
    assert gate.should_block(decision) is False
