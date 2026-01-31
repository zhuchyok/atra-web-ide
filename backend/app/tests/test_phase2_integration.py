"""
Интеграционный тест Фазы 2: классификатор, RAG-light, метрики рекомендаций.
Запуск: cd backend && python -m pytest app/tests/test_phase2_integration.py -v
"""
import asyncio
from unittest.mock import AsyncMock, patch

from app.services.query_classifier import classify_query, analyze_complexity
from app.services.rag_light import RAGLightService
from app.metrics.agent_suggestions import AgentSuggestionMetrics, AgentSuggestionMetric


def test_classifier_simple_factual_complex():
    """Классификатор: simple, factual, complex."""
    r = classify_query("привет")
    assert r["type"] == "simple"

    r = classify_query("сколько стоит подписка?")
    assert r["type"] == "factual"

    r = classify_query("проанализируй мои логи и дай рекомендации")
    assert r["type"] == "complex"


def test_analyze_complexity_suggest():
    """analyze_complexity: для сложных — suggest_agent True."""
    r = analyze_complexity("привет")
    assert r["suggest_agent"] is False

    r = analyze_complexity("сколько стоит подписка?")
    assert r["suggest_agent"] is False

    r = analyze_complexity("проанализируй мои логи и дай рекомендации")
    assert r["suggest_agent"] is True
    assert r["complexity_score"] >= 0.6


def test_rag_light_extract():
    """RAGLightService.extract_direct_answer."""
    svc = RAGLightService(enabled=False, max_response_length=150)
    out = svc.extract_direct_answer(
        "сколько стоит подписка?",
        "Стоимость подписки составляет 999 рублей в месяц.",
    )
    assert out
    assert "999" in out or "составляет" in out.lower()


def test_rag_light_fast_fact_answer_mocked():
    """RAG-light fast_fact_answer с замоканным search_one_chunk."""
    async def _run():
        svc = RAGLightService(enabled=True, knowledge_os=None)
        with patch.object(svc, "search_one_chunk", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = ("Стоимость 999 рублей в месяц.", 0.85)
            return await svc.fast_fact_answer("сколько стоит подписка?", timeout_ms=5000)

    answer = asyncio.run(_run())
    assert answer is not None
    assert "999" in answer or "составляет" in answer.lower()


def test_agent_suggestion_metrics():
    """Метрики рекомендаций Agent."""
    metrics = AgentSuggestionMetrics()
    metrics.add_suggestion(
        AgentSuggestionMetric(
            query="test",
            suggested=True,
            complexity_score=0.8,
            reason="test",
            user_action="accepted",
        )
    )
    stats = metrics.get_stats()
    assert stats["total_queries"] == 1
    assert stats["suggestion_rate"] == 1.0
