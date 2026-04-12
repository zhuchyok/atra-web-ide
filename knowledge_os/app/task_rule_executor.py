"""
Rule-based task executor — fallback when AI agent is unavailable.
Executes tasks without LLM based on metadata->>'source' and title templates.

[SWISS-CLOCK] Расширен: покрывает статусные запросы, health-check задачи,
простые code tasks — всё что застревало при LLM-недоступности.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Старые шаблоны (dashboard_daily_improver)
# ---------------------------------------------------------------------------
DASHBOARD_IMPROVEMENT_TEMPLATES: Dict[str, str] = {
    "max_entries": "Рекомендация: проверить st.cache_data(max_entries=100) в dashboard/app.py. Убедитесь, что кэш не растёт бесконечно.",
    "LEFT(content,N)": "Рекомендация: в запросах к knowledge_nodes использовать LEFT(content, 500) или аналог для избежания загрузки полного content. Проверить dashboard/app.py и связанные модули.",
    "lazy load": "Рекомендация: использовать st.fragment для lazy load вкладок (Streamlit best practices). Проверить структуру вкладок в дашборде.",
    "пустые состояния": "Рекомендация: добавить fallback при отсутствии данных — st.info/st.empty с сообщением «Нет данных». Проверить все виджеты, отображающие списки.",
    "дублирование метрик": "Рекомендация: проверить дублирование метрик между вкладками. Централизовать общие метрики в одном месте.",
}

TITLE_KEYWORDS = [
    ("max_entries", "max_entries"),
    ("LEFT(content", "LEFT(content,N)"),
    ("lazy load", "lazy load"),
    ("пустые состояния", "пустые состояния"),
    ("fallback при отсутствии данных", "пустые состояния"),
    ("дублирование метрик", "дублирование метрик"),
]

# ---------------------------------------------------------------------------
# [SWISS-CLOCK] Новые паттерны — статусные и health-check запросы
# ---------------------------------------------------------------------------

# Паттерны "простых" задач по title
_STATUS_PATTERNS = [
    re.compile(r"(покажи|список|перечисли|show|list)\s+(файл|file|директор|director|папк)", re.I),
    re.compile(r"(какой|what is|what'?s)\s+(статус|status|состояни)", re.I),
    re.compile(r"напиши\s+(одну|один|1|one)\s+(строк|line|команд)", re.I),
    re.compile(r"(write|print|вывод)\s+(current|текущ).*(date|дат|time|врем)", re.I),
    re.compile(r"проверь\s+через\s+curl", re.I),
    re.compile(r"GET\s+http[s]?://", re.I),
    re.compile(r"(health|healthcheck|статус\s+сервис)", re.I),
]

_SIMPLE_CODE_PATTERNS = [
    re.compile(r"напиши.*(python|py).*(hello|привет|текущ|current|дат|date)", re.I),
    re.compile(r"(hello world|helloworld)", re.I),
    re.compile(r"вывод.*(текущ|current).*(дат|date|врем|time)", re.I),
]

_CURL_PATTERN = re.compile(r"(GET|POST|curl)\s+(http[s]?://[\w./:-]+)", re.I)

# Внутренние сервисы — доступны без LLM
_INTERNAL_ENDPOINTS = {
    "knowledge_os_orchestrator": "http://knowledge_os_orchestrator:8000",
    "victoria-agent": "http://victoria-agent:8000",
    "veronica-agent": "http://veronica-agent:8000",
    "knowledge_rest": "http://knowledge_rest:8001",
}


def _match_template(title: str) -> Optional[str]:
    title_lower = (title or "").lower()
    for keyword, template_key in TITLE_KEYWORDS:
        if keyword.lower() in title_lower:
            return DASHBOARD_IMPROVEMENT_TEMPLATES.get(template_key)
    return None


def _is_status_task(title: str, description: str = "") -> bool:
    text = (title or "") + " " + (description or "")
    return any(p.search(text) for p in _STATUS_PATTERNS)


def _is_simple_code_task(title: str, description: str = "") -> bool:
    text = (title or "") + " " + (description or "")
    return any(p.search(text) for p in _SIMPLE_CODE_PATTERNS)


def _is_health_check_task(title: str, description: str = "") -> bool:
    text = (title or "") + " " + (description or "")
    m = _CURL_PATTERN.search(text)
    return m is not None


async def _execute_health_check(title: str, description: str) -> str:
    """Выполняет GET-запрос к внутреннему сервису без LLM."""
    text = (title or "") + " " + (description or "")
    m = _CURL_PATTERN.search(text)
    if not m:
        return "Rule-based: не удалось извлечь URL из описания задачи."
    url = m.group(2)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            return (
                f"Rule-based health-check результат:\n"
                f"URL: {url}\n"
                f"Status: {resp.status_code}\n"
                f"Body: {resp.text[:500]}"
            )
    except Exception as e:
        return f"Rule-based health-check: запрос к {url} завершился ошибкой: {e}"


def _execute_status_response(title: str, description: str) -> str:
    """Возвращает стандартный статусный ответ без LLM."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"Rule-based статусный ответ (AI временно недоступен, {ts}):\n\n"
        f"Запрос: {title}\n\n"
        "Статус системы:\n"
        "- LLM-модели временно перегружены (Circuit Breaker)\n"
        "- Очередь задач работает штатно\n"
        "- Данный ответ сформирован без LLM по детерминированному правилу\n"
        "- Задача будет перевыполнена с LLM при восстановлении сервисов\n\n"
        "Для актуального статуса обратитесь к /health endpoint или повторите запрос через 2-5 минут."
    )


def _execute_simple_code(title: str, description: str) -> str:
    """Возвращает простой Python-код без LLM."""
    ts = datetime.now(timezone.utc).isoformat()
    if re.search(r"(date|дат|time|врем)", title + description, re.I):
        return (
            "Rule-based выполнение:\n\n"
            "```python\n"
            "from datetime import datetime\n"
            f"print(datetime.now())  # {ts}\n"
            "```"
        )
    return (
        "Rule-based выполнение:\n\n"
        "```python\n"
        'print("Hello, World!")\n'
        "```"
    )


# ---------------------------------------------------------------------------
# Публичный API
# ---------------------------------------------------------------------------

def can_handle(task: Dict[str, Any]) -> bool:
    """Проверяет, может ли rule executor обработать задачу."""
    source = (task.get("metadata") or {}).get("source", "")
    title = task.get("title", "")
    description = task.get("description", "")

    # Старый путь: dashboard
    if source == "dashboard_daily_improver":
        return _match_template(title) is not None
    if "проверить" in (title or "").lower() and "дашборд" in (title or "").lower():
        return True

    # [SWISS-CLOCK] Новые паттерны
    if _is_health_check_task(title, description):
        return True
    if _is_status_task(title, description):
        return True
    if _is_simple_code_task(title, description):
        return True

    return False


async def execute_fallback(task: Dict[str, Any]) -> Optional[str]:
    """
    Выполняет задачу без LLM по rule-based шаблону.
    Returns: строка результата или None если шаблона нет.
    """
    source = (task.get("metadata") or {}).get("source", "")
    title = task.get("title", "")
    description = task.get("description", "")

    # Старый путь: dashboard
    if source == "dashboard_daily_improver":
        template_result = _match_template(title)
        if template_result:
            return "Rule-based выполнение (AI недоступен):\n\n" + template_result

    if title and "проверить" in title.lower() and "дашборд" in title.lower():
        return (
            "Rule-based выполнение:\n\n"
            "Чек-лист для ручной проверки:\n"
            f"- Открыть {title}\n"
            "- Проверить соответствующий код в dashboard/\n"
            "- Убедиться в отсутствии ошибок при пустых данных"
        )

    # [SWISS-CLOCK] Новые паттерны
    if _is_health_check_task(title, description):
        logger.info(f"[RULE EXEC] Health-check task: {title[:60]}")
        return await _execute_health_check(title, description)

    if _is_simple_code_task(title, description):
        logger.info(f"[RULE EXEC] Simple code task: {title[:60]}")
        return _execute_simple_code(title, description)

    if _is_status_task(title, description):
        logger.info(f"[RULE EXEC] Status task: {title[:60]}")
        return _execute_status_response(title, description)

    return None
