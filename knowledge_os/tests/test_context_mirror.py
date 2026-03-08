import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_os.app.context_mirror import ContextMirror


class TestContextMirror:
    @pytest.fixture
    def redis_mock(self):
        with patch("redis.asyncio.from_url") as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_save_context_success(self, redis_mock):
        # Setup
        mock_client = AsyncMock()
        mock_pipeline = AsyncMock()

        # Настройка пайплайна
        mock_client.pipeline.return_value = mock_pipeline
        redis_mock.return_value = mock_client

        mirror = ContextMirror(redis_url="redis://localhost:6379")

        session_id = "test_session"
        history = [{"role": "user", "content": "hello"}]

        # Execute
        result = await mirror.save_context(session_id, history)

        # Verify
        assert result is True
        mock_pipeline.delete.assert_called_once_with("context:list:test_session")
        mock_pipeline.rpush.assert_called_once_with(
            "context:list:test_session", json.dumps(history[0])
        )
        mock_pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_context_success_list(self, redis_mock):
        # Setup
        mock_client = AsyncMock()
        redis_mock.return_value = mock_client
        history = [{"role": "user", "content": "hello"}]
        mock_client.lrange.return_value = [json.dumps(m) for m in history]

        mirror = ContextMirror(redis_url="redis://localhost:6379")
        session_id = "test_session"

        # Execute
        result = await mirror.get_context(session_id)

        # Verify
        assert result == history
        mock_client.lrange.assert_called_once_with("context:list:test_session", 0, -1)

    @pytest.mark.asyncio
    async def test_get_context_success_fallback(self, redis_mock):
        # Setup
        mock_client = AsyncMock()
        redis_mock.return_value = mock_client
        history = [{"role": "user", "content": "hello"}]
        mock_client.lrange.return_value = []
        mock_client.get.return_value = json.dumps(history)

        mirror = ContextMirror(redis_url="redis://localhost:6379")
        session_id = "test_session"

        # Execute
        result = await mirror.get_context(session_id)

        # Verify
        assert result == history
        mock_client.get.assert_called_once_with("context:test_session")

    @pytest.mark.asyncio
    async def test_get_context_not_found(self, redis_mock):
        # Setup
        mock_client = AsyncMock()
        redis_mock.return_value = mock_client
        mock_client.lrange.return_value = []
        mock_client.get.return_value = None

        mirror = ContextMirror(redis_url="redis://localhost:6379")
        session_id = "unknown_session"

        # Execute
        result = await mirror.get_context(session_id)

        # Verify
        assert result is None

    @pytest.mark.asyncio
    async def test_save_context_redis_failure(self, redis_mock):
        # Setup
        mock_client = AsyncMock()
        redis_mock.return_value = mock_client
        mock_client.pipeline.side_effect = Exception("Redis connection error")

        mirror = ContextMirror(redis_url="redis://localhost:6379")
        session_id = "test_session"
        history = [{"role": "user", "content": "hello"}]

        # Execute
        result = await mirror.save_context(session_id, history)

        # Verify (graceful degradation)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_context_redis_failure(self, redis_mock):
        # Setup
        mock_client = AsyncMock()
        redis_mock.return_value = mock_client
        mock_client.lrange.side_effect = Exception("Redis connection error")

        mirror = ContextMirror(redis_url="redis://localhost:6379")
        session_id = "test_session"

        # Execute
        result = await mirror.get_context(session_id)

        # Verify (graceful degradation)
        assert result is None
