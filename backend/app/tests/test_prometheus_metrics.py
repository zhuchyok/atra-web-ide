"""
Тесты Prometheus метрик (День 5).
"""
import asyncio
import pytest
from app.metrics.prometheus_metrics import (
    metrics,
    USER_REQUESTS,
    RAG_REQUESTS,
    record_cache_hit,
    update_cache_size,
    get_metrics,
)


def test_record_cache_hit():
    """Запись попадания в кэш не падает."""
    record_cache_hit("test_cache")


def test_update_cache_size():
    """Обновление размера кэша не падает."""
    update_cache_size("test_cache", 42)


def test_get_metrics_returns_bytes():
    """get_metrics возвращает bytes в формате Prometheus."""
    data = get_metrics()
    assert isinstance(data, bytes)
    text = data.decode("utf-8")
    assert "chat_requests_total" in text or "rag_" in text or "plan_" in text or "# HELP" in text


@pytest.mark.asyncio
async def test_metrics_track_request_decorator():
    """Декоратор track_request не ломает async функцию."""
    @metrics.track_request(mode="ask", endpoint="test")
    async def test_function():
        return "success"

    result = await test_function()
    assert result == "success"


@pytest.mark.asyncio
async def test_metrics_track_rag_decorator():
    """Декоратор track_rag не ломает async функцию."""
    @metrics.track_rag(mode="ask", rag_type="rag_light")
    async def test_rag():
        return "answer"

    result = await test_rag()
    assert result == "answer"
