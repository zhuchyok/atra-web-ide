import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from app.local_router import LocalAIRouter
from app.memory.journal_manager import ExpertJournalManager


def test_journal_metadata_normalization_defaults():
    meta = ExpertJournalManager._normalize_memory_metadata({})
    assert meta["memory_type"] == "episodic"
    assert 0.0 <= meta["confidence"] <= 1.0
    assert meta["source"] == "expert_journal"
    assert meta["policy_version"] == "v1"
    assert meta["used_in_decision"] is False
    assert isinstance(meta["expires_at"], str) and meta["expires_at"]


def test_journal_metadata_normalization_invalid_type_fallback():
    meta = ExpertJournalManager._normalize_memory_metadata(
        {"memory_type": "invalid_type", "confidence": 7}
    )
    assert meta["memory_type"] == "episodic"
    assert meta["confidence"] == 1.0


@pytest.mark.asyncio
async def test_routing_journal_publish_calls_redis_xadd():
    router = LocalAIRouter()
    mock_client = AsyncMock()

    with patch("app.redis_manager.redis_manager.get_client", new=AsyncMock(return_value=mock_client)):
        await router._publish_routing_journal(
            task_type="smoke",
            category="chat",
            selected_route="ollama_studio",
            selected_model="victoria-wisdom-24k:latest",
            selected_node="Mac Studio (Ollama)",
            candidate_nodes=["Mac Studio (MLX)", "Mac Studio (Ollama)"],
            latency_ms=12.34,
            success=True,
            reason="smoke",
        )

    mock_client.xadd.assert_awaited_once()
    args, kwargs = mock_client.xadd.await_args
    assert args[0] == "stream:routing_decisions"
    assert kwargs["maxlen"] == 10000
    assert kwargs["approximate"] is True
