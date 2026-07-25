"""Tests for canary_router.py — A/B testing for expert mutations."""

import pytest


class TestCanaryRouter:
    """Test canary routing logic without external dependencies."""

    def test_should_use_canary_imports(self):
        """canary_router module should be importable."""
        from app.canary_router import record_canary_result, should_use_canary

        assert callable(should_use_canary)
        assert callable(record_canary_result)

    @pytest.mark.asyncio
    async def test_judge_responses(self):
        """Test the response comparison heuristics."""
        from app.canary_router import _judge_responses

        # Canary is significantly longer -> win
        assert await _judge_responses("short", "longer detailed response here") == "canary"

        # Production is longer -> win
        assert await _judge_responses("long detailed response here", "short") == "production"

        # Similar length / identical -> draw (no fake win)
        assert await _judge_responses("same length", "same len here") == "draw"
        assert await _judge_responses("identical", "identical") == "draw"

        # Production error -> canary wins
        assert (
            await _judge_responses("[SYSTEM: All LLM sources unavailable]", "good response")
            == "canary"
        )

        # Empty production -> canary wins
        assert await _judge_responses("", "response") == "canary"

        # Canary error -> production wins
        assert await _judge_responses("good response", "[SYSTEM: error]") == "production"

    def test_canary_traffic_percent(self):
        """CANARY_TRAFFIC_PERCENT should be configurable."""
        import os

        pct = int(os.getenv("CANARY_TRAFFIC_PERCENT", "10"))
        assert 0 <= pct <= 100

    @pytest.mark.asyncio
    async def test_run_llm_uses_dialogue_llm_not_missing_symbol(self, monkeypatch):
        """Daemon must not call non-existent ai_core._run_local_llm."""
        from app import canary_router

        async def fake_gen(prompt, **kwargs):
            return "bullet one\nbullet two\nbullet three"

        monkeypatch.setattr(
            "app.dialogue_llm.generate_dialogue_text",
            fake_gen,
            raising=False,
        )
        # Patch import path used inside _run_llm
        import sys
        import types

        mod = types.ModuleType("dialogue_llm")
        mod.generate_dialogue_text = fake_gen
        monkeypatch.setitem(sys.modules, "dialogue_llm", mod)

        text = await canary_router._run_llm("USER REQUEST: hi")
        assert "bullet" in text
