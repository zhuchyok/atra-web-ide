import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Setup path for imports
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from app.local_router import LocalAIRouter


@pytest.fixture
def mock_context_mirror():
    mirror = AsyncMock()
    mirror.get_context.return_value = []
    mirror.save_context.return_value = True
    return mirror


@pytest.mark.asyncio
async def test_context_saved_before_mlx_call(mock_context_mirror):
    """Test that context is saved to Redis before calling MLX."""
    router = LocalAIRouter()
    router.context_mirror = mock_context_mirror

    # Mock health check to return MLX node first
    router.check_health = AsyncMock(
        return_value=[
            {
                "name": "MLX",
                "url": "http://localhost:11435",
                "priority": 0,
                "routing_key": "mlx_studio",
            }
        ]
    )

    # Mock the actual HTTP call to succeed
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.json.return_value = {"message": {"content": "MLX response"}}

        result = await router.run_local_llm("Hello", session_id="test_session")

        # Verify context_mirror.save_context was called
        mock_context_mirror.save_context.assert_called()


@pytest.mark.asyncio
async def test_failover_uses_mirrored_context(mock_context_mirror):
    """Test that if MLX fails, Ollama is called."""
    router = LocalAIRouter()
    router.context_mirror = mock_context_mirror

    # Mock health check to return MLX then Ollama
    router.check_health = AsyncMock(
        return_value=[
            {
                "name": "MLX",
                "url": "http://localhost:11435",
                "priority": 0,
                "routing_key": "mlx_studio",
            },
            {
                "name": "Ollama",
                "url": "http://localhost:11434",
                "priority": 1,
                "routing_key": "ollama_studio",
            },
        ]
    )

    # Mock HTTP calls: first (MLX) fails, second (Ollama) succeeds
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # MLX fails with 500
        mock_mlx_resp = MagicMock(status_code=500)
        # Ollama succeeds
        mock_ollama_resp = MagicMock(status_code=200)
        mock_ollama_resp.json.return_value = {"message": {"content": "Ollama response"}}

        mock_post.side_effect = [mock_mlx_resp, mock_ollama_resp]

        result = await router.run_local_llm("Hello", session_id="test_session")

        # Verify failover reached Ollama even if router-level retries add extra calls.
        assert mock_post.call_count >= 2
        assert "Ollama response" in str(result)


@pytest.mark.asyncio
async def test_predictive_warmup_skipped_for_wisdom_reasoning():
    """Wisdom KV warmup on Ollama 11434 is the faucet; skip it."""
    router = LocalAIRouter()
    router._trigger_predictive_warmup = AsyncMock()
    router._select_model = MagicMock(return_value="victoria-wisdom-24k:latest")
    router.check_health = AsyncMock(
        return_value=[
            {
                "name": "MLX",
                "url": "http://localhost:11435",
                "priority": 0,
                "routing_key": "mlx_studio",
            },
            {
                "name": "Ollama",
                "url": "http://localhost:11434",
                "priority": 1,
                "routing_key": "ollama_studio",
            },
        ]
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.json.return_value = {"message": {"content": "Response"}}

        await router.run_local_llm("Analyze this", category="reasoning")

        router._trigger_predictive_warmup.assert_not_called()


@pytest.mark.asyncio
async def test_predictive_warmup_triggered_for_non_wisdom():
    router = LocalAIRouter()
    router._trigger_predictive_warmup = AsyncMock()
    router._select_model = MagicMock(return_value="phi3.5:3.8b")
    router.check_health = AsyncMock(
        return_value=[
            {
                "name": "MLX",
                "url": "http://localhost:11435",
                "priority": 0,
                "routing_key": "mlx_studio",
            },
            {
                "name": "Ollama",
                "url": "http://localhost:11434",
                "priority": 1,
                "routing_key": "ollama_studio",
            },
        ]
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.json.return_value = {"message": {"content": "Response"}}

        await router.run_local_llm("Analyze this", category="reasoning", model="phi3.5:3.8b")

        router._trigger_predictive_warmup.assert_called_once()


@pytest.mark.asyncio
async def test_empty_mlx_does_not_fallback_wisdom_to_ollama(mock_context_mirror):
    """MLX empty must not POST victoria-wisdom* to Ollama 11434."""
    router = LocalAIRouter()
    router.context_mirror = mock_context_mirror
    router._trigger_predictive_warmup = AsyncMock()
    router.check_health = AsyncMock(
        return_value=[
            {
                "name": "MLX",
                "url": "http://localhost:11435",
                "priority": 0,
                "routing_key": "mlx_studio",
            },
            {
                "name": "Ollama",
                "url": "http://localhost:11434",
                "priority": 1,
                "routing_key": "ollama_studio",
            },
        ]
    )

    posted = []

    async def fake_post(url, json=None, **kwargs):
        posted.append((str(url), (json or {}).get("model")))
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"message": {"content": ""}}
        resp.text = ""
        return resp

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = fake_post
        await router.run_local_llm("Analyze this deeply", category="reasoning")

    ollama_wisdom = [
        (u, m)
        for u, m in posted
        if "11434" in u and m and "victoria-wisdom" in str(m).lower()
    ]
    assert ollama_wisdom == []
