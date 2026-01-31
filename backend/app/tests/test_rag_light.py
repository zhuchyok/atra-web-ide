"""
Тесты RAG-light: extract_direct_answer и классификация запросов (без бэкенда).
Запуск: cd backend && python -m pytest app/tests/test_rag_light.py -v
"""
import pytest


def _truncate(text: str, max_len: int = 150) -> str:
    if len(text) <= max_len:
        return text.strip()
    t = text[:max_len]
    last = t.rfind(" ")
    if last > max_len // 2:
        t = t[:last]
    return t.strip() + "..."


def test_extract_direct_answer_logic():
    """Логика извлечения ответа из чанка (как в RAGLightService.extract_direct_answer)."""
    test_chunk = "Стоимость подписки составляет 999 рублей в месяц. Включены все функции."
    query = "сколько стоит подписка?"
    keywords = ("составляет", "равно", "стоит", "является")
    for s in test_chunk.replace(".\n", ". ").split(". "):
        s = s.strip()
        if not s:
            continue
        if any(kw in s.lower() for kw in keywords) and any(c.isdigit() for c in s):
            answer = _truncate(s)
            assert "999" in answer or "составляет" in answer.lower()
            return
    pytest.fail("No matching sentence found in test chunk")


def test_classify_query_simple():
    """Простые запросы → type simple."""
    from app.services.query_classifier import classify_query

    for q in ["привет", "здравствуй", "спасибо", "пока", "ок"]:
        r = classify_query(q)
        assert r.get("type") == "simple", f"Expected simple for '{q}', got {r}"


def test_classify_query_factual():
    """Фактуальные запросы → type factual."""
    from app.services.query_classifier import classify_query

    for q in ["сколько стоит подписка?", "что такое Docker?", "какой порт у бэкенда?"]:
        r = classify_query(q)
        assert r.get("type") == "factual", f"Expected factual for '{q}', got {r}"


def test_classify_query_complex():
    """Сложные запросы → type complex."""
    from app.services.query_classifier import classify_query

    r = classify_query("проанализируй логи и предложи оптимизацию")
    assert r.get("type") == "complex", f"Expected complex, got {r}"


def test_analyze_complexity_suggests_agent():
    """Сложные запросы получают suggest_agent=True."""
    from app.services.query_classifier import analyze_complexity

    r = analyze_complexity("проанализируй мои логи и найди ошибки")
    assert r.get("suggest_agent") is True, r
    assert r.get("complexity_score", 0) >= 0.5


def test_analyze_complexity_no_suggest_simple():
    """Простые запросы — suggest_agent=False."""
    from app.services.query_classifier import analyze_complexity

    r = analyze_complexity("привет")
    assert r.get("suggest_agent") is False, r


def test_rag_light_extract_direct_answer():
    """RAGLightService.extract_direct_answer на тестовом чанке."""
    from app.services.rag_light import RAGLightService

    svc = RAGLightService(enabled=False, max_response_length=150)
    chunk = "Стоимость подписки составляет 999 рублей в месяц."
    out = svc.extract_direct_answer("сколько стоит подписка?", chunk)
    assert out
    assert "999" in out or "составляет" in out.lower()
