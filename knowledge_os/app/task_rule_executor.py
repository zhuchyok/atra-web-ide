"""
Rule-based task executor — fallback when AI agent is unavailable.
Executes tasks without LLM based on metadata->>'source' and title templates.
Part of Resilient Task Execution plan (Этап 3).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Шаблоны для dashboard_daily_improver (Этап 4 плана)
DASHBOARD_IMPROVEMENT_TEMPLATES: Dict[str, str] = {
    "max_entries": "Рекомендация: проверить st.cache_data(max_entries=100) в dashboard/app.py. Убедитесь, что кэш не растёт бесконечно.",
    "LEFT(content,N)": "Рекомендация: в запросах к knowledge_nodes использовать LEFT(content, 500) или аналог для избежания загрузки полного content. Проверить dashboard/app.py и связанные модули.",
    "lazy load": "Рекомендация: использовать st.fragment для lazy load вкладок (Streamlit best practices). Проверить структуру вкладок в дашборде.",
    "пустые состояния": "Рекомендация: добавить fallback при отсутствии данных — st.info/st.empty с сообщением «Нет данных». Проверить все виджеты, отображающие списки.",
    "дублирование метрик": "Рекомендация: проверить дублирование метрик между вкладками. Централизовать общие метрики в одном месте.",
}

# Ключевые слова в title для маппинга
TITLE_KEYWORDS = [
    ("max_entries", "max_entries"),
    ("LEFT(content", "LEFT(content,N)"),
    ("lazy load", "lazy load"),
    ("пустые состояния", "пустые состояния"),
    ("fallback при отсутствии данных", "пустые состояния"),
    ("дублирование метрик", "дублирование метрик"),
]


def _match_template(title: str) -> Optional[str]:
    """Находит шаблон по ключевым словам в title."""
    title_lower = (title or "").lower()
    for keyword, template_key in TITLE_KEYWORDS:
        if keyword.lower() in title_lower:
            return DASHBOARD_IMPROVEMENT_TEMPLATES.get(template_key)
    return None


async def execute_fallback(task: Dict[str, Any]) -> Optional[str]:
    """
    Выполняет задачу без LLM по rule-based шаблону.
    
    Returns:
        Строка результата или None, если подходящего шаблона нет.
    """
    source = (task.get("metadata") or {}).get("source", "")
    title = task.get("title", "")
    
    if source == "dashboard_daily_improver":
        template_result = _match_template(title)
        if template_result:
            header = "Rule-based выполнение (AI недоступен):\n\n"
            return header + template_result
    
    # Общий шаблон для задач «Проверить X»
    if title and "проверить" in title.lower() and "дашборд" in title.lower():
        return (
            "Rule-based выполнение:\n\n"
            "Чек-лист для ручной проверки:\n"
            f"- Открыть {title}\n"
            "- Проверить соответствующий код в dashboard/\n"
            "- Убедиться в отсутствии ошибок при пустых данных"
        )
    
    return None


def can_handle(task: Dict[str, Any]) -> bool:
    """Проверяет, может ли rule executor обработать задачу (есть ли шаблон)."""
    source = (task.get("metadata") or {}).get("source", "")
    title = task.get("title", "")
    if source == "dashboard_daily_improver":
        return _match_template(title) is not None
    if "проверить" in (title or "").lower() and "дашборд" in (title or "").lower():
        return True
    return False
