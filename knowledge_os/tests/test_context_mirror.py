"""
Unit tests for ContextMirror (Redis integration).
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from app.context_mirror import ContextMirror

@pytest.fixture
def mock_redis():
    with patch("redis.from_url") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock_instance

@pytest.mark.asyncio
async def test_save_context(mock_redis):
    mirror = ContextMirror("redis://localhost:6379/0")
    session_id = "test_session"
    history = [{"role": "user", "content": "hello"}]
    
    await mirror.save_context(session_id, history)
    
    # Check that redis.set was called with the correct key and serialized history
    mock_redis.set.assert_called_once_with(
        f"context:{session_id}", 
        json.dumps(history), 
        ex=3600
    )

@pytest.mark.asyncio
async def test_get_context(mock_redis):
    mirror = ContextMirror("redis://localhost:6379/0")
    session_id = "test_session"
    history = [{"role": "user", "content": "hello"}]
    mock_redis.get.return_value = json.dumps(history)
    
    result = await mirror.get_context(session_id)
    
    assert result == history
    mock_redis.get.assert_called_once_with(f"context:{session_id}")

@pytest.mark.asyncio
async def test_get_context_empty(mock_redis):
    mirror = ContextMirror("redis://localhost:6379/0")
    session_id = "empty_session"
    mock_redis.get.return_value = None
    
    result = await mirror.get_context(session_id)
    
    assert result == []
    mock_redis.get.assert_called_once_with(f"context:{session_id}")
