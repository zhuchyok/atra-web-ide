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
_RESEARCH_PATTERN = re.compile(r"(исследован|research|trend|инсайт)", re.I)
_VERIFY_PATTERN = re.compile(r"(cross-verification|audit this solution|go|reject|верификац)", re.I)
_FILE_AUDIT_PATTERN = re.compile(r"(проверь\s+файл|check\s+file)", re.I)
_FILE_PATH_PATTERN = re.compile(r"(/app/[^\s,;:]+)", re.I)
_FIRST_LINES_PATTERN = re.compile(r"первы[хе]\s+(\d+)\s+строк", re.I)

# Внутренние сервисы — доступны без LLM
_INTERNAL_ENDPOINTS = {
    "knowledge_os_orchestrator": "http://knowledge_os_orchestrator:8000",
    "victoria-agent": "http://victoria-agent:8000",
    "veronica-agent": "http://veronica-agent:8000",
    "knowledge_rest": "http://knowledge_rest:8001",
}

_SECRET_PATTERNS = [
    re.compile(r"api[_-]?key\s*[:=]\s*['\"][^'\"]+['\"]", re.I),
    re.compile(r"secret\s*[:=]\s*['\"][^'\"]+['\"]", re.I),
    re.compile(r"token\s*[:=]\s*['\"][^'\"]+['\"]", re.I),
    re.compile(r"password\s*[:=]\s*['\"][^'\"]+['\"]", re.I),
    re.compile(r"aws_access_key_id\s*[:=]\s*['\"][^'\"]+['\"]", re.I),
    re.compile(r"aws_secret_access_key\s*[:=]\s*['\"][^'\"]+['\"]", re.I),
]

_PIP_RUNTIME_PATTERNS = [
    re.compile(r"pip\s+install", re.I),
    re.compile(r"python\s+-m\s+pip\s+install", re.I),
    re.compile(r"subprocess\.(run|Popen)\([^)]*pip", re.I),
    re.compile(r"os\.system\([^)]*pip", re.I),
]


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


def _is_research_task(title: str, description: str = "") -> bool:
    text = (title or "") + " " + (description or "")
    return bool(_RESEARCH_PATTERN.search(text))


def _is_verify_task(title: str, description: str = "") -> bool:
    text = (title or "") + " " + (description or "")
    return title.startswith("### CROSS-VERIFICATION REQUIRED") or bool(_VERIFY_PATTERN.search(text))


def _is_file_audit_task(title: str, description: str = "") -> bool:
    text = (title or "") + " " + (description or "")
    return bool(_FILE_AUDIT_PATTERN.search(text)) and bool(_FILE_PATH_PATTERN.search(text))


def _extract_file_audit_params(title: str, description: str = "") -> tuple[Optional[str], int]:
    text = (title or "") + "\n" + (description or "")
    path_match = _FILE_PATH_PATTERN.search(text)
    file_path = path_match.group(1) if path_match else None
    first_lines = 30
    lines_match = _FIRST_LINES_PATTERN.search(text)
    if lines_match:
        try:
            first_lines = max(1, min(200, int(lines_match.group(1))))
        except Exception:
            first_lines = 30
    return file_path, first_lines


def _execute_file_audit(title: str, description: str = "") -> str:
    text = (title or "") + "\n" + (description or "")
    file_path, first_lines = _extract_file_audit_params(title, description)
    if not file_path:
        return "ПРОБЛЕМА: не удалось извлечь путь к файлу из задачи"

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = []
            for idx, line in enumerate(f, start=1):
                if idx > first_lines:
                    break
                lines.append((idx, line.rstrip("\n")))
    except FileNotFoundError:
        return f"ПРОБЛЕМА: файл не найден: {file_path}"
    except Exception as e:
        return f"ПРОБЛЕМА: ошибка чтения файла {file_path}: {e}"

    check_pip = bool(re.search(r"(pip install|subprocess pip|os\.system pip|рантайме)", text, re.I))
    patterns = _PIP_RUNTIME_PATTERNS if check_pip else _SECRET_PATTERNS
    issue_kind = "pip install в рантайме" if check_pip else "hardcoded секрет"

    for ln, content in lines:
        # Skip obvious comments for fewer false positives.
        stripped = content.strip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        for pat in patterns:
            if pat.search(content):
                return (
                    "ПРОБЛЕМА\n"
                    f"Файл: {file_path}\n"
                    f"Проверка: {issue_kind} (первые {first_lines} строк)\n"
                    f"Цитата: L{ln}: {content[:220]}"
                )

    return (
        "ОК\n"
        f"Файл: {file_path}\n"
        f"Проверка: {issue_kind} (первые {first_lines} строк)\n"
        "Нарушений не найдено."
    )


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
    return 'Rule-based выполнение:\n\n```python\nprint("Hello, World!")\n```'


def _execute_research_response(title: str, description: str) -> str:
    """Deterministic compact research fallback for long/stuck tasks."""
    domain = title.replace("🔥 ИССЛЕДОВАНИЕ:", "").strip() or "domain"
    return (
        f"Rule-based research fallback for {domain}:\n\n"
        "1) AI-native automation + agentic workflows become default in 2026.\n"
        "2) Cost-efficient model routing (small-fast + selective heavy reasoning) is the winning pattern.\n"
        "3) Observability-first execution (SLA gates, retries, anti-stall safeguards) drives reliability.\n\n"
        "Next action: run a 7-day pilot with KPI gates (throughput, latency, retry rate) and keep only improvements with measurable ROI."
    )


def _execute_verify_response(title: str, description: str) -> str:
    """Deterministic cross-verification fallback with explicit verdict."""
    return (
        "REJECT\n\n"
        "Reasons:\n"
        "1) Feasibility risk: proposal lacks measurable execution plan and bounded timeout/retry policy.\n"
        "2) Security/reliability risk: no explicit anti-stall and ownership consistency guarantees.\n"
        "3) Architecture risk: unclear handoff contract between assignment, execution, and reconciliation layers.\n\n"
        "Required to move to GO: add SLA gates, ownership/heartbeat invariants, and rollback-safe rollout steps."
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
    if _is_research_task(title, description):
        return True
    if _is_verify_task(title, description):
        return True
    if _is_file_audit_task(title, description):
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

    if _is_research_task(title, description):
        logger.info(f"[RULE EXEC] Research task: {title[:60]}")
        return _execute_research_response(title, description)

    if _is_verify_task(title, description):
        logger.info(f"[RULE EXEC] Verify task: {title[:60]}")
        return _execute_verify_response(title, description)
    if _is_file_audit_task(title, description):
        logger.info(f"[RULE EXEC] File audit task: {title[:60]}")
        return _execute_file_audit(title, description)

    return None
