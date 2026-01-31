#!/usr/bin/env python3
"""
Синхронизация списка сотрудников из единого источника (configs/experts/employees.json).

После добавления нового сотрудника в employees.json запустите:
  python scripts/sync_employees.py

Скрипт обновит:
  1. configs/experts/_known_names_generated.py — KNOWN_EXPERT_NAMES для check_experts_count.py
  2. knowledge_os/db/seed_experts.json — role, department; новых сотрудников добавит с шаблонным system_prompt
  3. configs/experts/employees.md — таблица сотрудников (генерируется из JSON)
"""

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EMPLOYEES_JSON = REPO_ROOT / "configs" / "experts" / "employees.json"
KNOWN_NAMES_PY = REPO_ROOT / "configs" / "experts" / "_known_names_generated.py"
SEED_JSON = REPO_ROOT / "knowledge_os" / "db" / "seed_experts.json"
EMPLOYEES_MD = REPO_ROOT / "configs" / "experts" / "employees.md"

SYSTEM_PROMPT_TEMPLATE = "You are {name}, {role}.\n- Выполняйте задачи в рамках своей роли и отдела {department}\n- Согласуйте результат с контекстом проекта"


def load_employees():
    with open(EMPLOYEES_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("employees", []), data.get("updated", "")


def write_known_names(employees):
    names = sorted({e["name"] for e in employees})
    lines = [
        "# Auto-generated from configs/experts/employees.json — do not edit by hand",
        "# Run: python scripts/sync_employees.py",
        "",
        "KNOWN_EXPERT_NAMES = {",
    ]
    for n in names:
        lines.append(f"    {json.dumps(n)},")
    lines.append("}")
    KNOWN_NAMES_PY.parent.mkdir(parents=True, exist_ok=True)
    with open(KNOWN_NAMES_PY, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  ✅ {KNOWN_NAMES_PY.relative_to(REPO_ROOT)} ({len(names)} имён)")


def merge_seed(employees):
    by_name = {e["name"]: e for e in employees}
    seed = []
    if SEED_JSON.exists():
        with open(SEED_JSON, "r", encoding="utf-8") as f:
            seed = json.load(f)
    existing_names = {e["name"] for e in seed}
    new_seed = []
    for i, emp in enumerate(employees):
        name, role, department = emp["name"], emp["role"], emp["department"]
        existing = next((e for e in seed if e["name"] == name), None)
        if existing:
            entry = {
                "name": name,
                "role": role,
                "department": department,
                "system_prompt": existing.get("system_prompt", SYSTEM_PROMPT_TEMPLATE.format(name=name, role=role, department=department)),
                "metadata": existing.get("metadata", {"original_id": str(i + 1)}),
            }
        else:
            entry = {
                "name": name,
                "role": role,
                "department": department,
                "system_prompt": SYSTEM_PROMPT_TEMPLATE.format(name=name, role=role, department=department),
                "metadata": {"original_id": str(i + 1)},
            }
        new_seed.append(entry)
    SEED_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(SEED_JSON, "w", encoding="utf-8") as f:
        json.dump(new_seed, f, ensure_ascii=False, indent=2)
    added = len(employees) - len(existing_names)
    print(f"  ✅ {SEED_JSON.relative_to(REPO_ROOT)} ({len(new_seed)} экспертов, добавлено новых: {added})")


def write_employees_md(employees, updated):
    departments = sorted({e["department"] for e in employees})
    lines = [
        "# Сотрудники ATRA (полный список с ролями)",
        "",
        "**Единый источник правды:** добавьте нового сотрудника в **`configs/experts/employees.json`**, затем запустите: **`python scripts/sync_employees.py`** — обновятся seed, KNOWN_EXPERT_NAMES и эта таблица.",
        "",
        f"- **Итого сотрудников:** {len(employees)}",
        f"- **Отделов:** {len(departments)}",
        f"- **Обновлено:** {updated}",
        "",
        f"## Полный список ({len(employees)})",
        "",
        "| № | Имя | Роль | Отдел |",
        "|---|-----|------|-------|",
    ]
    for i, e in enumerate(employees, 1):
        lines.append(f"| {i} | {e['name']} | {e['role']} | {e['department']} |")
    lines.extend([
        "",
        f"**Итого: {len(employees)} сотрудников.**",
        "",
        "## Правило для будущего",
        "",
        "**При добавлении нового сотрудника:**",
        "",
        "1. Добавьте запись в **`configs/experts/employees.json`** в массив `employees`: `{\"name\": \"Имя\", \"role\": \"Роль\", \"department\": \"Отдел\"}`.",
        "2. Сделайте **git add** и **git commit**. Если один раз выполнили **`./scripts/install_git_hooks.sh`**, при коммите автоматически запустится sync и в коммит попадут:",
        "   - `configs/experts/_known_names_generated.py` (KNOWN_EXPERT_NAMES),",
        "   - `knowledge_os/db/seed_experts.json` (role, department; новый эксперт добавится с шаблонным system_prompt),",
        "   - эта таблица в `configs/experts/employees.md`.",
        "3. При необходимости добавьте роль в `.cursor/rules/` и связь в `configs/experts/team.md`.",
        "4. Для БД: примените seed/миграцию или добавьте запись в таблицу `experts`.",
        "",
        "## Системная роль: Оркестратор",
        "",
        "**Оркестратор** — не отдельный сотрудник, а системная роль координации задач. Подробно: **`.cursor/rules/22_orchestrator.md`**. В Cursor: `@orchestrator`.",
        "",
        "## Связь с другими файлами",
        "",
        "- **Основные роли и Cursor:** `configs/experts/team.md`",
        "- **Seed для БД:** `knowledge_os/db/seed_experts.json`",
        "- **Department Heads:** `knowledge_os/app/department_heads_system.py`",
        "",
    ])
    with open(EMPLOYEES_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  ✅ {EMPLOYEES_MD.relative_to(REPO_ROOT)}")


def main():
    if not EMPLOYEES_JSON.exists():
        print(f"❌ Не найден {EMPLOYEES_JSON}")
        return 1
    employees, updated = load_employees()
    if not employees:
        print("❌ В employees.json нет массива employees или он пуст")
        return 1
    print("Синхронизация сотрудников из configs/experts/employees.json...")
    write_known_names(employees)
    merge_seed(employees)
    write_employees_md(employees, updated)
    print("Готово.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
