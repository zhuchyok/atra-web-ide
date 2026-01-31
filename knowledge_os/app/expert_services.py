"""
Expert Services — список сотрудников и их услуг для вставки в промпты и планирование.

Оркестратор, Виктория и Вероника используют этот блок при составлении промптов и планов,
чтобы точно знать, к кому делегировать и кого привлекать для помощи.
Источник: configs/experts/employees.json (единый источник правды).
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Пути к employees.json: из knowledge_os/app/ → ../../configs/experts (atra-web-ide)
# или из корня knowledge_os при запуске из контейнера
_EMPLOYEES_PATHS = [
    Path(__file__).resolve().parent.parent.parent / "configs" / "experts" / "employees.json",  # atra-web-ide
    Path(__file__).resolve().parent.parent / "configs" / "experts" / "employees.json",
    Path("/app/configs/experts/employees.json"),
    Path(os.getenv("EMPLOYEES_JSON", "")),
]
_EMPLOYEES_CACHE: Optional[List[Dict[str, Any]]] = None


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
    if not employees:
        return "Список экспертов не загружен. Делегируй по ролям: стратегия — Павел, риск — Мария, данные — Максим, код — Игорь, архитектура — Виктория."

    if by_department:
        dept_map: Dict[str, List[Dict]] = {}
        for e in employees[: max_entries * 2]:
            dept = e.get("department") or "Other"
            dept_map.setdefault(dept, []).append(e)
        parts = []
        for dept in sorted(dept_map.keys()):
            names = [f"{e.get('name', '')} ({e.get('role', '')})" for e in dept_map[dept][:15]]
            parts.append(f"{dept}: " + ", ".join(names))
        return "\n".join(parts)

    parts = [
        f"{e.get('name', '')} ({e.get('role', '')}) — {e.get('department', '')}"
        for e in employees[:max_entries]
    ]
    return separator.join(parts)


def get_expert_services_for_planning() -> str:
    """
    Короткий блок для промптов планирования (MASTER_PLAN, декомпозиция).
    Умещается в контекст и подсказывает, кого назначать на разделы.
    """
    employees = _load_employees()
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


def list_experts_by_role(role_substring: str) -> List[Dict[str, Any]]:
    """
    Возвращает сотрудников, у которых в роли встречается role_substring.
    Для выбора конкретного эксперта по роли.
    """
    employees = _load_employees()
    sub = role_substring.lower()
    return [e for e in employees if sub in (e.get("role") or "").lower()]
