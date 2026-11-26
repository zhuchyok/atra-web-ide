"""E2E tests: full task lifecycle without LLM calls. Uses Redis."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_llm():
    with patch("app.ai_core.run_smart_agent_async", new=AsyncMock(return_value="Mock response")):
        yield


@pytest.fixture
async def bb():
    import app.redis_manager as rm
    import app.services.blackboard_service as bs

    # Reset singletons for fresh Redis connection on each test
    bs._blackboard = None
    rm.RedisManager._instance = None
    rm.redis_manager = rm.RedisManager()
    # Clear test keys
    import os

    import redis.asyncio as aioredis

    url = os.getenv("REDIS_URL", "redis://localhost:6381")
    client = await aioredis.from_url(url, decode_responses=True)
    for key in await client.keys("*e2e_*"):
        await client.delete(key)
    await client.aclose()
    bb = bs.get_blackboard_service()
    return bb


class TestE2EFullCycle:
    async def test_auction_resolves_winner_with_highest_bid(self, bb, mock_llm):
        task_id = "e2e_happy"
        await bb.post_goal(task_id, "Write a unit test", {"priority": "high"})
        await bb.post_bid(task_id, "Анна", 0.85)
        await bb.post_bid(task_id, "Роман", 0.75)
        winner = await bb.resolve_auction(task_id)
        assert winner == "Анна"

    async def test_counter_offer_skips_overloaded_expert(self, bb, mock_llm):
        task_id = "e2e_counter"
        await bb.post_goal(task_id, "Heavy analysis", {"resource_intensity": "extreme"})
        await bb.counter_offer(task_id, "Анна", "overload", "load=3")
        await bb.post_bid(task_id, "Анна", 0.95)
        await bb.post_bid(task_id, "Роман", 0.50)
        winner = await bb.resolve_auction(task_id)
        assert winner is not None
        assert winner != "Анна"

    async def test_auction_returns_none_when_all_bids_below_threshold(self, bb, mock_llm):
        task_id = "e2e_low"
        await bb.post_goal(task_id, "Niche task", {})
        await bb.post_bid(task_id, "Анна", 0.1)
        await bb.post_bid(task_id, "Роман", 0.05)
        assert await bb.resolve_auction(task_id) is None

    async def test_claim_fails_if_heartbeat_already_owned(self, bb):
        task_id = "e2e_claim"
        client = await bb.redis.get_client()
        await client.set(f"blackboard:heartbeat:{task_id}", "other_worker", nx=True)
        result = await bb.claim_task(task_id, "Анна")
        assert result is False
