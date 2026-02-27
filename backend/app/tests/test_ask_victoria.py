"""
Тесты endpoint POST /api/chat/ask-victoria (Singularity 15.0).
Используем dependency_overrides, чтобы не зависеть от реальной Victoria.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import chat
from app.services.victoria import VictoriaClient


def _make_mock_client(run_return):
    mock_client = MagicMock(spec=VictoriaClient)
    mock_client.run = AsyncMock(return_value=run_return)
    return mock_client


@pytest.fixture
def client_success():
    async def _dep():
        return _make_mock_client({"status": "success", "result": "Done.", "response": "Done."})

    app.dependency_overrides[chat.get_victoria_client] = _dep
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(chat.get_victoria_client, None)


def test_ask_victoria_success_plain(client_success):
    resp = client_success.post(
        "/api/chat/ask-victoria",
        json={"goal": "Проверь бэкенд", "project_context": "atra-web-ide"},
    )
    assert resp.status_code == 200
    assert "Done" in resp.text
    assert resp.headers.get("content-type", "").startswith("text/plain")


def test_ask_victoria_success_json(client_success):
    resp = client_success.post(
        "/api/chat/ask-victoria",
        json={"goal": "Проверь бэкенд"},
        params={"format": "json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "Done" in data["result"]


@pytest.fixture
def client_error():
    async def _dep():
        return _make_mock_client({"status": "error", "error": "Unavailable"})

    app.dependency_overrides[chat.get_victoria_client] = _dep
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(chat.get_victoria_client, None)


def test_ask_victoria_error_503(client_error):
    resp = client_error.post("/api/chat/ask-victoria", json={"goal": "Задача"})
    assert resp.status_code == 503
    # Сообщение может быть на русском («недоступна») или английском (unavailable)
    assert "недоступна" in resp.text.lower() or "unavailable" in resp.text.lower()


@pytest.fixture
def client_clarification():
    async def _dep():
        return _make_mock_client(
            {
                "status": "success",
                "result": "",
                "clarification_questions": ["Какой проект?", "Какой срок?"],
            }
        )

    app.dependency_overrides[chat.get_victoria_client] = _dep
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(chat.get_victoria_client, None)


def test_ask_victoria_clarification(client_clarification):
    resp = client_clarification.post("/api/chat/ask-victoria", json={"goal": "Сделай отчёт"})
    assert resp.status_code == 200
    assert "уточнить" in resp.text or "Какой" in resp.text


def test_ask_victoria_user_key():
    mock_run = AsyncMock(return_value={"status": "success", "result": "Ok"})
    mock_client = MagicMock(spec=VictoriaClient)
    mock_client.run = mock_run

    async def _dep():
        return mock_client

    app.dependency_overrides[chat.get_victoria_client] = _dep
    try:
        with TestClient(app) as c:
            c.post("/api/chat/ask-victoria", json={"goal": "Память", "user_key": "openwebui-123"})
        call_kw = mock_run.call_args[1]
        assert call_kw.get("session_id") == "openwebui-123"
    finally:
        app.dependency_overrides.pop(chat.get_victoria_client, None)


def test_ask_victoria_empty_goal_422(client_success):
    """Пустая или только пробелы goal — 422."""
    resp = client_success.post("/api/chat/ask-victoria", json={"goal": "   "})
    assert resp.status_code == 422
    assert "goal" in resp.text.lower() or "required" in resp.text.lower()
