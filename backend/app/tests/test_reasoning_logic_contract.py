"""
Фаза 5 плана «Логика мысли»: контракт ответа Victoria.
Проверяем: needs_clarification → clarification_questions; knowledge.strategy, confidence в raw.
Запуск: pytest backend/app/tests/test_reasoning_logic_contract.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_fake_response(json_data: dict):
    """Синхронный response: .json() возвращает dict, .raise_for_status() — ничего."""
    r = MagicMock()
    r.json.return_value = json_data
    r.raise_for_status = MagicMock()
    return r


@pytest.mark.asyncio
async def test_victoria_client_needs_clarification_returns_questions():
    """При status=needs_clarification и clarification_questions клиент возвращает их."""
    from app.services.victoria import VictoriaClient

    fake_response = _make_fake_response({
        "status": "needs_clarification",
        "clarification_questions": ["Какой именно проект?", "За какой период?"],
        "output": "",
    })

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=fake_response)
        client = VictoriaClient(base_url="http://localhost:8010")
        result = await client.run("Сделай что-то по проекту")

    assert result["status"] == "needs_clarification"
    assert result.get("clarification_questions") == ["Какой именно проект?", "За какой период?"]
    assert result.get("raw", {}).get("clarification_questions") == ["Какой именно проект?", "За какой период?"]


@pytest.mark.asyncio
async def test_victoria_client_success_includes_knowledge_strategy_confidence():
    """При успешном ответе raw содержит knowledge.strategy и knowledge.confidence."""
    from app.services.victoria import VictoriaClient

    fake_response = _make_fake_response({
        "status": "success",
        "output": "Готово.",
        "knowledge": {
            "strategy": "quick_answer",
            "strategy_reason": "Простой запрос",
            "confidence": 0.9,
        },
    })

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=fake_response)
        client = VictoriaClient(base_url="http://localhost:8010")
        result = await client.run("Привет")

    assert result["status"] == "success"
    raw = result.get("raw", {})
    assert raw.get("knowledge", {}).get("strategy") == "quick_answer"
    assert raw.get("knowledge", {}).get("confidence") == 0.9
    assert raw.get("knowledge", {}).get("strategy_reason") == "Простой запрос"


@pytest.mark.asyncio
async def test_victoria_client_decline_includes_output():
    """При decline_or_redirect в output может быть причина и рекомендация."""
    from app.services.victoria import VictoriaClient

    fake_response = _make_fake_response({
        "status": "success",
        "output": "Эта задача вне моей компетенции. Обратитесь к отделу X.",
        "knowledge": {
            "strategy": "decline_or_redirect",
            "confidence": 0.85,
        },
    })

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=fake_response)
        client = VictoriaClient(base_url="http://localhost:8010")
        result = await client.run("Запрос вне scope")

    assert result["status"] == "success"
    assert "вне моей компетенции" in (result.get("result") or "")
    assert result.get("raw", {}).get("knowledge", {}).get("strategy") == "decline_or_redirect"
