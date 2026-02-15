"""
Тесты делегирования задач в Veronica: delegate_to_veronica (формат, таймаут, ошибки).
Используется mock aiohttp — без живого Veronica. Связь с docs/TESTING_FULL_SYSTEM.md.
Запуск: pytest backend/app/tests/test_veronica_delegate.py -v
"""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Корень репозитория для импорта src.agents.bridge (backend/app/tests -> parents[3] = repo root)
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from src.agents.bridge.enhanced_router import delegate_to_veronica


def _make_session_mock(status: int, json_payload: dict):
    """Мок aiohttp: session.post() возвращает response с status и json()."""
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value=json_payload)
    response.text = AsyncMock(return_value="")
    session = MagicMock()
    session.post.return_value.__aenter__ = AsyncMock(return_value=response)
    session.post.return_value.__aexit__ = AsyncMock(return_value=None)
    return session


@pytest.mark.asyncio
async def test_delegate_empty_goal_returns_none():
    """Пустой goal → None (без HTTP)."""
    assert await delegate_to_veronica("", "atra-web-ide", None) is None
    assert await delegate_to_veronica("   ", "atra-web-ide", "abc") is None


@pytest.mark.asyncio
async def test_delegate_200_returns_dict():
    """HTTP 200 + dict → dict с status, output, knowledge, correlation_id."""
    payload = {"status": "success", "output": "Список файлов: a, b", "knowledge": {"steps": []}}
    session = _make_session_mock(200, payload)
    with patch("aiohttp.ClientSession", return_value=MagicMock(__aenter__=AsyncMock(return_value=session), __aexit__=AsyncMock(return_value=None))):
        result = await delegate_to_veronica("покажи файлы", "atra-web-ide", "corr-123")
    assert result is not None
    assert result["status"] == "success"
    assert result["output"] == "Список файлов: a, b"
    assert result["knowledge"] == {"steps": []}
    assert result.get("correlation_id") == "corr-123"


@pytest.mark.asyncio
async def test_delegate_non_200_returns_none():
    """HTTP не 200 → None."""
    session = _make_session_mock(503, {"error": "overload"})
    with patch("aiohttp.ClientSession", return_value=MagicMock(__aenter__=AsyncMock(return_value=session), __aexit__=AsyncMock(return_value=None))):
        result = await delegate_to_veronica("покажи файлы", "atra-web-ide", None)
    assert result is None


@pytest.mark.asyncio
async def test_delegate_exception_returns_none():
    """Исключение (timeout/connection) → None."""
    session = MagicMock()
    session.post.return_value.__aenter__ = AsyncMock(side_effect=TimeoutError("timeout"))
    session.post.return_value.__aexit__ = AsyncMock(return_value=None)
    with patch("aiohttp.ClientSession", return_value=MagicMock(__aenter__=AsyncMock(return_value=session), __aexit__=AsyncMock(return_value=None))):
        result = await delegate_to_veronica("покажи файлы", "atra-web-ide", None)
    assert result is None


@pytest.mark.asyncio
async def test_delegate_response_not_dict_returns_none():
    """Ответ не dict (например список) → None."""
    session = _make_session_mock(200, ["not", "a", "dict"])
    with patch("aiohttp.ClientSession", return_value=MagicMock(__aenter__=AsyncMock(return_value=session), __aexit__=AsyncMock(return_value=None))):
        result = await delegate_to_veronica("покажи файлы", "atra-web-ide", None)
    assert result is None
