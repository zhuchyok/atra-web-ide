"""Роутер консилиума: выбор движка (соло-совет vs дебаты) по категории темы.

Основан на данных A/B-битв (solo vs debate, judge victoria-wisdom-24k):
  configs/evals/results/battle_*.json — агрегат по категориям (2026-09-23):
    соло сильнее:   code_audit, communication, code_generation, analysis, devops, debugging
    дебаты сильнее: testing, research, security
    паритет:        architecture (по умолчанию дебаты — больше итераций на синтез)
Решение по роутингу пересматривается по мере накопления ночных битв
(launchd com.atra.consilium-battle-nightly, 01:30 ежедневно).
"""

from __future__ import annotations

import re
from typing import Literal

Engine = Literal["sequential", "debate"]

# Категория -> отсечка для дебатов. Всё, что не замапилось, — категория "architecture".
DEBATE_CATEGORIES = {"testing", "research", "security", "architecture"}

# Ключевые слова (RU/EN) для классификации темы. Порядок не важен:
# побеждает категория с наибольшим числом совпадений.
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "communication": (
        "привет", "здравствуй", "как дела", "что ты умеешь", "кто ты",
        "статус проекта", "статус", "расскажи о", "объясни доступно",
        "hello", "hi ", "how are you", "what can you do",
    ),
    "code_audit": (
        "аудит", "ревью", "review", "найди проблему", "проблема в коде",
        "проверь код", "проверь файл", "code smell", "уязвимость в коде",
        "что не так с кодом", "баг в коде",
    ),
    "code_generation": (
        "напиши код", "напиши функцию", "напиши скрипт", "сгенерируй",
        "одна строка кода", "реализуй", "write a function", "implement",
    ),
    "testing": (
        "тест", "тесты", "тестирован", "покрытие", "pytest", "unittest",
        "test coverage", "напиши тест",
    ),
    "research": (
        "исследуй", "проанализируй рынок", "сравни подходы", "изучи",
        "обзор технологий", "research", "investigate", "поиск решений",
    ),
    "security": (
        "безопасность", "уязвимост", "pentest", "xss", "sql-инъекц",
        "security", "шифрован", "аутентификац", "авторизац",
    ),
    "debugging": (
        "отлад", "дебаг", "debug", "почему падает", "ошибка в", "не работает",
        "исключение", "stacktrace", "трейс",
    ),
    "devops": (
        "деплой", "deploy", "docker", "kubernetes", "ci/cd", "мониторинг",
        "бэкап", "backup", "инфраструктур", "nginx",
    ),
    "analysis": (
        "проанализируй", "анализ данных", "метрик", "статистик",
        "анализ ", "analyze",
    ),
}

_WORD_RE = re.compile(r"[\w-]+")


def classify_category(topic: str) -> str:
    """Классификация темы по ключевым словам. Порог — 1 совпадение."""
    t = (topic or "").lower()
    if not t.strip():
        return "architecture"
    scores: dict[str, int] = {}
    for cat, kws in CATEGORY_KEYWORDS.items():
        hits = sum(1 for kw in kws if kw in t)
        if hits:
            scores[cat] = hits
    if not scores:
        return "architecture"
    return max(scores.items(), key=lambda kv: kv[1])[0]


def resolve_engine(topic: str) -> tuple[Engine, str]:
    """Вернуть (движок, категория) для темы.

    sequential — соло-совет экспертов (быстрее и точнее для простых категорий),
    debate — мультиагентные дебаты (research/testing/security/architecture).
    """
    category = classify_category(topic)
    engine: Engine = "debate" if category in DEBATE_CATEGORIES else "sequential"
    return engine, category
