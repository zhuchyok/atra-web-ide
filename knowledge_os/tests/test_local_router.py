import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Setup path for imports
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
# v150.79 _get_adaptive_options -> ollama_slot_pin: модулю нужен сам каталог app в sys.path
_app_root = os.path.join(_root, "app")
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)

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
    # [v150.x] Анти-спиральный бэкофф — глобальное состояние модуля; без сброса
    # загрязняется предыдущими тестами (в CI без живых узлов) и меняет путь failover.
    import app.local_router as _lr

    _lr._LLM_FAIL_STREAK = 0
    _lr._LLM_LAST_FAIL_TS = None
    router.context_mirror = mock_context_mirror
    # [v150.x] Сканер моделей дергает живой /api/tags и меняет выбор модели — замораживаем.
    router._refresh_available_models = AsyncMock()
    # [v150.10] BRAIN-SOLO-GATE: при живом hands-узле 11437 модели рук не идут на
    # 11434 — в этом тесте проверяем именно failover MLX→Ollama, убираем hands-узел.
    router.nodes = [n for n in router.nodes if "11437" not in str(n.get("url", ""))]
    # Выбор модели зависит от модульного кэша сканера (загрязняется другими тестами) —
    # фиксируем детерминированно: тест про failover и зеркалирование, не про селекцию.
    router._select_model = MagicMock(return_value="phi3.5:3.8b-stable")
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

    # Mock HTTP calls: first (MLX) fails, second (Ollama) succeeds.
    # [v149.26] NODE-GATE «модель × узел» сверяет модель со списком /api/tags узла
    # (кэш 120с в _node_models_cache). В тестах нет живых узлов — сеем кэш напрямую,
    # иначе гейт молча пропускает оба узла и POST не происходит вовсе.
    import time as _time

    for _url in ("http://localhost:11435", "http://localhost:11434"):
        router._node_models_cache[_url] = {"phi3.5:3.8b-stable", "phi3.5:3.8b"}
        router._node_models_ts[_url] = _time.time()

    async def fake_post(url, json=None, **kwargs):
        if "11435" in str(url):
            return MagicMock(status_code=500)  # MLX fails
        resp = MagicMock(status_code=200)  # Ollama succeeds
        resp.json.return_value = {"message": {"content": "Ollama response"}}
        return resp

    # Failover обязан подхватить зеркальную историю сессии для Ollama-запроса.
    mock_context_mirror.get_context.return_value = [
        {"role": "user", "content": "earlier mirrored turn"}
    ]

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = fake_post

        result = await router.run_local_llm("Hello", session_id="test_session")

        # Failover дошёл до Ollama (11434) и вернул его ответ.
        assert mock_post.call_count >= 1
        ollama_calls = [
            c for c in mock_post.call_args_list if "11434" in str(c.args[0] if c.args else c.kwargs.get("url", ""))
        ]
        assert ollama_calls, "failover must POST to the Ollama node"
        assert "Ollama response" in str(result)
        # Зеркальный контекст подмешан в сообщения Ollama-запроса.
        sent_messages = ollama_calls[0].kwargs.get("json", {}).get("messages", [])
        assert any("earlier mirrored turn" in str(m.get("content", "")) for m in sent_messages)


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
