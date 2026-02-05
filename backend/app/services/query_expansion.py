"""
Query expansion: расширение запроса синонимами и ключевыми терминами
для улучшения retrieval (Фаза 4).
"""
import re
from typing import List, Optional

# Маппинг запросов → дополнительные термины (из эталонных ответов)
# Помогает эмбеддингу запроса быть ближе к релевантному чанку
QUERY_EXPANSION_TERMS: dict[str, str] = {
    "сколько стоит подписка": "подписка стоимость 999 рублей месяц",
    "как создать аккаунт": "регистрация email пароль создать",
    "время работы поддержки": "поддержка 9:00 21:00 московское",
    "документация API": "API docs Swagger redoc endpoint chat",
    "как сбросить пароль": "пароль сброс забыли восстановление email",
    "тарифы и цены": "тариф 999 1999 руб подписка корпоративный",
    "контакты поддержки": "email support telegram чат 24/7",
    "как отменить подписку": "отмена подписки настройки аккаунта",
    "справка по использованию": "справка help Ask Agent режимы",
    "часто задаваемые вопросы": "FAQ faq тарифы интеграция API",
    "как настроить Victoria": "Victoria VICTORIA_URL порт 8010 config настраивается конфигурация backend app config.py",
    "что такое RAG": "RAG retrieval generation поиск генерация",
    "порты сервисов": "порты 8080 8010 11434 11435 5432 6381 (Redis на хосте)",
    "как запустить проект локально": "docker-compose frontend npm run dev",
    "метрики Prometheus": "metrics Prometheus rag_requests victoria /metrics rag_duration",
}


def expand_query(query: str, max_extra_terms: int = 8) -> str:
    """
    Расширяет запрос дополнительными терминами для улучшения retrieval.
    Возвращает: "original_query expansion_terms"
    """
    if not query or not query.strip():
        return query
    q_lower = query.strip().lower()
    # Точное совпадение
    extra = QUERY_EXPANSION_TERMS.get(q_lower)
    if extra:
        terms = extra.split()[:max_extra_terms]
        return f"{query} {' '.join(terms)}"
    # Частичное совпадение (подстрока)
    for key, terms in QUERY_EXPANSION_TERMS.items():
        if key in q_lower or q_lower in key:
            add = terms.split()[:max_extra_terms]
            return f"{query} {' '.join(add)}"
    return query


def expand_query_fallback(query: str) -> str:
    """
    Лёгкое расширение: добавляет частые термины из БЗ для коротких запросов.
    """
    if not query or len(query.split()) >= 4:
        return query
    # Короткие запросы типа "поддержка", "тарифы" → добавляем контекст
    q_lower = query.lower()
    fallbacks = [
        ("поддержк", "email telegram чат контакт"),
        ("тариф", "цена подписка руб"),
        ("контакт", "email support чат"),
        ("пароль", "сброс восстановление"),
        ("api", "документация endpoint"),
        ("запуск", "docker npm"),
        ("порт", "8080 8010"),
        ("victoria", "VICTORIA_URL config backend настройка"),
        ("prometheus", "metrics rag_requests victoria duration"),
    ]
    for substr, terms in fallbacks:
        if substr in q_lower:
            return f"{query} {terms}"
    return query
