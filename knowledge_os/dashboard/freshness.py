"""Классификация свежести источников дашборда. Без Streamlit/psycopg2."""

RARE_EVENT_SOURCES = frozenset({"okrs", "simulations", "file_comments"})
OPERATIONAL_STALE_MINUTES = 24 * 60


def classify_source_freshness(source: str, age_minutes) -> tuple[str, bool]:
    """Вернуть (метка статуса, считать ли источником для красного warning).

    Редкие источники не поднимают «Обнаружены устаревшие источники»:
    отсутствие новых OKR/симуляций ≠ сломанная вкладка.
    """
    if age_minutes is None:
        return "⚪ нет данных", False
    age = float(age_minutes)
    if source in RARE_EVENT_SOURCES:
        if age <= 60:
            return "🟢 актуально", False
        if age <= 90 * 24 * 60:
            return "🟢 редко (норма)", False
        return "🟡 давно не было событий", False
    if age <= 60:
        return "🟢 актуально", False
    if age <= OPERATIONAL_STALE_MINUTES:
        return "🟡 устаревает", False
    return "🔴 устарело", True
