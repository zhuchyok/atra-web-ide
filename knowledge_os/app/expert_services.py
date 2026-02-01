"""
Expert Services — список сотрудников и их услуг для вставки в промпты и планирование.

Оркестратор, Виктория и Вероника используют этот блок при составлении промптов и планов,
чтобы точно знать, к кому делегировать и кого привлекать для помощи.
Источник: configs/experts/employees.json + experts из БД (гибрид: employees + автономные).
"""

import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
_DB_EXPERTS_CACHE: Optional[List[Dict[str, Any]]] = None
_DB_EXPERTS_TS = 0.0
_DB_EXPERTS_LOCK = threading.Lock()
_DB_EXPERTS_TTL = 60

# Пути к employees.json: из knowledge_os/app/ → ../../configs/experts (atra-web-ide)
# или из корня knowledge_os при запуске из контейнера
_EMPLOYEES_PATHS = [
    Path(__file__).resolve().parent.parent.parent / "configs" / "experts" / "employees.json",  # atra-web-ide
    Path(__file__).resolve().parent.parent / "configs" / "experts" / "employees.json",
    Path("/app/configs/experts/employees.json"),
    Path(os.getenv("EMPLOYEES_JSON", "")),
]
_EMPLOYEES_CACHE: Optional[List[Dict[str, Any]]] = None


def _load_experts_from_db() -> List[Dict[str, Any]]:
    """Загружает экспертов из БД (в т.ч. автономно нанятых). TTL 60 сек. Синхронно через thread."""
    global _DB_EXPERTS_CACHE, _DB_EXPERTS_TS
    now = time.time()
    with _DB_EXPERTS_LOCK:
        if now - _DB_EXPERTS_TS < _DB_EXPERTS_TTL and _DB_EXPERTS_CACHE is not None:
            return _DB_EXPERTS_CACHE

    def _fetch():
        try:
            import asyncio
            import asyncpg
            async def _run():
                conn = await asyncpg.connect(DB_URL)
                rows = await conn.fetch("SELECT name, role, department FROM experts")
                await conn.close()
                return [{"name": r["name"], "role": r["role"], "department": r["department"]} for r in rows]
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_run())
            finally:
                loop.close()
        except Exception as e:
            logger.debug("expert_services: DB load failed: %s", e)
            return []

    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_fetch)
            result = future.result(timeout=10)
    except Exception as e:
        logger.debug("expert_services: DB fetch error: %s", e)
        result = []
    with _DB_EXPERTS_LOCK:
        _DB_EXPERTS_CACHE = result
        _DB_EXPERTS_TS = time.time()
    return result


def _load_employees() -> List[Dict[str, Any]]:
    """Загружает список сотрудников из employees.json."""
    global _EMPLOYEES_CACHE
    if _EMPLOYEES_CACHE is not None:
        return _EMPLOYEES_CACHE
    for path in _EMPLOYEES_PATHS:
        if path and str(path) and Path(path).exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                employees = data.get("employees", data) if isinstance(data, dict) else data
                if isinstance(employees, list):
                    _EMPLOYEES_CACHE = employees
                    return _EMPLOYEES_CACHE
            except Exception as e:
                logger.debug("expert_services: load %s failed: %s", path, e)
    _EMPLOYEES_CACHE = []
    return _EMPLOYEES_CACHE


def get_expert_services_text(
    max_entries: int = 30,
    by_department: bool = False,
    separator: str = "; ",
) -> str:
    """
    Возвращает текст «Доступные эксперты и услуги» для вставки в промпты и планы.

    Args:
        max_entries: максимум записей (чтобы не раздувать промпт)
        by_department: группировать по отделам
        separator: разделитель между записями

    Returns:
        Строка вида: "Павел (Trading Strategy Developer) — Trading; Мария (Risk Manager) — Risk Management; ..."
    """
    employees = _load_employees()
    db_experts = _load_experts_from_db()
    by_name = {e.get("name"): e for e in employees if e.get("name")}
    for e in db_experts:
        if e.get("name") and e["name"] not in by_name:
            by_name[e["name"]] = e
    merged = list(by_name.values())

    if not merged:
        return "Список экспертов не загружен. Делегируй по ролям: стратегия — Павел, риск — Мария, данные — Максим, код — Игорь, архитектура — Виктория."

    if by_department:
        dept_map: Dict[str, List[Dict]] = {}
        for e in merged[: max_entries * 2]:
            dept = e.get("department") or "Other"
            dept_map.setdefault(dept, []).append(e)
        parts = []
        for dept in sorted(dept_map.keys()):
            names = [f"{e.get('name', '')} ({e.get('role', '')})" for e in dept_map[dept][:15]]
            parts.append(f"{dept}: " + ", ".join(names))
        return "\n".join(parts)

    parts = [
        f"{e.get('name', '')} ({e.get('role', '')}) — {e.get('department', '')}"
        for e in merged[:max_entries]
    ]
    return separator.join(parts)


def get_expert_services_for_planning() -> str:
    """
    Короткий блок для промптов планирования (MASTER_PLAN, декомпозиция).
    Умещается в контекст и подсказывает, кого назначать на разделы.
    """
    employees = _load_employees()
    db_experts = _load_experts_from_db()
    by_name = {e.get("name"): e for e in employees if e.get("name")}
    for e in db_experts:
        if e.get("name") and e["name"] not in by_name:
            by_name[e["name"]] = e
    employees = list(by_name.values())
    if not employees:
        return (
            "Роли для разделов плана: индикаторы/фильтры — Павел (Trading Strategy Developer); "
            "риск-менеджмент — Мария (Risk Manager); оптимизация/тесты — Максим (Data Analyst); "
            "код/архитектура — Игорь (Backend), Виктория (Team Lead)."
        )
    # Собираем по ролям, релевантным для плана
    role_keywords = {
        "Trading": "индикаторы, фильтры, стратегия",
        "Risk": "риск, SL/TP, position sizing",
        "Data Analyst": "оптимизация, тесты, метрики",
        "Backend": "код, API, архитектура",
        "Team Lead": "координация, итоговый план",
        "ML Engineer": "модели, данные",
    }
    by_role: Dict[str, List[str]] = {}
    for e in employees:
        role = e.get("role") or ""
        name = e.get("name") or ""
        for kw, label in role_keywords.items():
            if kw.lower() in role.lower():
                by_role.setdefault(label, []).append(f"{name} ({role})")
                break
    lines = [f"- {label}: " + ", ".join(names[:3]) for label, names in sorted(by_role.items())]
    return "Доступные эксперты по разделам плана:\n" + "\n".join(lines) if lines else get_expert_services_text(20)


def get_expert_services_for_prompt() -> str:
    """
    Блок для вставки в role-aware промпты (Query Orchestrator, Виктория).
    «При необходимости делегируй или опирайся на услуги сотрудников: ...»
    """
    text = get_expert_services_text(25, by_department=False)
    return f"При необходимости делегируй или привлекай услуги сотрудников: {text}"


def get_expert_system_prompt(expert_name_or_role: str) -> Optional[str]:
    """
    Получить system_prompt эксперта из БД (fallback для prompt_templates при неизвестных экспертах).
    Для автономно нанятых и экспертов без шаблона в PROMPT_TEMPLATES.
    Ищет по name или по role (для ролей вроде "Competitive Intelligence Director").
    Поддерживает Veronica→Вероника, Victoria→Виктория.
    """
    def _fetch():
        try:
            import asyncio
            import asyncpg
            try:
                from app.expert_aliases import resolve_expert_name_for_db
                resolved = resolve_expert_name_for_db(expert_name_or_role)
            except ImportError:
                resolved = expert_name_or_role
            async def _run():
                conn = await asyncpg.connect(DB_URL)
                row = await conn.fetchrow(
                    "SELECT system_prompt FROM experts WHERE name = $1 OR role = $1 LIMIT 1",
                    resolved,
                )
                if not row and resolved != expert_name_or_role:
                    row = await conn.fetchrow(
                        "SELECT system_prompt FROM experts WHERE name = $1 OR role = $1 LIMIT 1",
                        expert_name_or_role,
                    )
                await conn.close()
                return row["system_prompt"] if row and row.get("system_prompt") else None
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_run())
            finally:
                loop.close()
        except Exception as e:
            logger.debug("expert_services: get_system_prompt failed: %s", e)
            return None

    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(_fetch).result(timeout=5)
    except Exception:
        return None


def get_all_expert_names(max_count: Optional[int] = None) -> List[str]:
    """
    Возвращает имена всех экспертов (employees.json + БД).
    Для Swarm/Consensus — состав растёт динамически.
    """
    employees = _load_employees()
    db_experts = _load_experts_from_db()
    by_name = {e.get("name"): e for e in employees if e.get("name")}
    for e in db_experts:
        if e.get("name") and e["name"] not in by_name:
            by_name[e["name"]] = e
    names = list(by_name.keys())
    if max_count is not None and max_count > 0:
        names = names[:max_count]
    return names


def list_experts_by_role(role_substring: str) -> List[Dict[str, Any]]:
    """
    Возвращает сотрудников, у которых в роли встречается role_substring.
    Для выбора конкретного эксперта по роли. Включает автономно нанятых из БД.
    """
    employees = _load_employees()
    db_experts = _load_experts_from_db()
    by_name = {e.get("name"): e for e in employees if e.get("name")}
    for e in db_experts:
        if e.get("name") and e["name"] not in by_name:
            by_name[e["name"]] = e
    employees = list(by_name.values())
    sub = role_substring.lower()
    return [e for e in employees if sub in (e.get("role") or "").lower()]
