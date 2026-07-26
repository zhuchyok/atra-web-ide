"""Local-first agent bridge: no Cursor CLI binary."""

import sys
from types import ModuleType
from unittest.mock import AsyncMock

import pytest
from app.victoria_local_agent import generate_local


@pytest.mark.asyncio
async def test_generate_local_uses_ai_core_first():
    fake = ModuleType("ai_core")
    fake.run_smart_agent_async = AsyncMock(return_value="mutated prompt text that is long enough")
    sys.modules["ai_core"] = fake
    try:
        out = await generate_local("evolve this expert", category="reasoning")
        assert out and "mutated" in out
        fake.run_smart_agent_async.assert_awaited_once()
    finally:
        sys.modules.pop("ai_core", None)


@pytest.mark.asyncio
async def test_generate_local_prefer_router():
    fake_router_mod = ModuleType("local_router")

    class FakeRouter:
        async def run_local_llm(self, *_a, **_k):
            return ("local wisdom answer xx", "phi3.5:3.8b")

    fake_router_mod.LocalAIRouter = FakeRouter
    sys.modules["local_router"] = fake_router_mod
    try:
        out = await generate_local(
            "prompt", category="reasoning", prefer_router=True, model_hint="phi3.5:3.8b"
        )
        assert out and "local wisdom" in out
    finally:
        sys.modules.pop("local_router", None)


def test_enhanced_evolver_has_no_cursor_binary_path():
    import inspect

    import app.enhanced_expert_evolver as mod

    src = inspect.getsource(mod)
    assert "/root/.local/bin/cursor-agent" not in src
    assert "victoria_local_agent" in src
