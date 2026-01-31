"""
Тесты fallback стратегий эмбеддингов (Фаза 3, день 3–4).
Запуск: cd backend && python -m pytest app/tests/test_embedding_fallback.py -v
"""
from app.services.embedding_fallback import EmbeddingFallback


def test_fallback_stats():
    """Статистика fallback."""
    fallback = EmbeddingFallback()
    stats = fallback.get_stats()
    assert "local_model_available" in stats
    assert "keyword_fallback_enabled" in stats
    assert stats["keyword_fallback_enabled"] is True


def test_hybrid_search():
    """Гибридный поиск комбинирует векторные и keyword результаты."""
    fallback = EmbeddingFallback()
    vector_results = [("content1", 0.8), ("content2", 0.6)]
    keyword_results = [("content2", 0.9), ("content3", 0.7)]
    hybrid = fallback.hybrid_search(
        query="test",
        vector_results=vector_results,
        keyword_results=keyword_results,
        vector_weight=0.7,
    )
    assert len(hybrid) == 3
    contents = [c for c, _ in hybrid]
    assert "content2" in contents
    assert "content1" in contents
    assert "content3" in contents
