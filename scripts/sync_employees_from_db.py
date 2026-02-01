#!/usr/bin/env python3
"""
Синхронизация employees.json из БД — сделать список актуальным.

БД может содержать больше экспертов (автономный найм, миграции).
Скрипт подтягивает недостающих в employees.json и запускает sync_employees.py.

Запуск:
  python scripts/sync_employees_from_db.py
  python scripts/sync_employees_from_db.py --dry-run  # только показать, не писать

  # Если asyncpg не в PATH, используйте venv:
  backend/.venv/bin/python scripts/sync_employees_from_db.py
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EMPLOYEES_JSON = REPO_ROOT / "configs" / "experts" / "employees.json"
DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


async def fetch_experts_from_db():
    """Загрузить экспертов из БД."""
    try:
        import asyncpg
    except ImportError:
        print("❌ asyncpg не установлен. Используйте: backend/.venv/bin/python scripts/sync_employees_from_db.py")
        return []
    try:
        conn = await asyncpg.connect(DB_URL)
        rows = await conn.fetch(
            "SELECT name, role, department FROM experts WHERE name IS NOT NULL AND name != '' ORDER BY name"
        )
        await conn.close()
        return [{"name": r["name"], "role": r["role"] or "TBD", "department": r["department"] or "General"} for r in rows]
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return []


def load_employees():
    """Загрузить employees.json."""
    if not EMPLOYEES_JSON.exists():
        return [], {}
    with open(EMPLOYEES_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    employees = data.get("employees", [])
    meta = {k: v for k, v in data.items() if k != "employees"}
    return employees, meta


def merge_db_into_employees(employees, db_experts):
    """
    Объединить: employees + эксперты из БД, которых нет в employees.
    Сохраняем порядок: сначала все из employees, затем новые из БД (по имени).
    """
    by_name = {e["name"]: e for e in employees}
    added = []
    for expert in db_experts:
        name = expert.get("name")
        if not name:
            continue
        if name not in by_name:
            by_name[name] = expert
            added.append(expert)
    if not added:
        return employees, 0
    # Новый список: существующие + добавленные (отсортированы по имени)
    result = list(employees)
    for ex in sorted(added, key=lambda x: x["name"]):
        result.append(ex)
    return result, len(added)


def main():
    parser = argparse.ArgumentParser(description="Синхронизировать employees.json из БД")
    parser.add_argument("--dry-run", action="store_true", help="Только показать изменения, не писать")
    args = parser.parse_args()

    db_experts = asyncio.run(fetch_experts_from_db())
    if not db_experts:
        print("⚠️ Нет экспертов в БД или БД недоступна")
        return 1

    employees, meta = load_employees()
    if not employees and not meta:
        print("❌ Не найден employees.json")
        return 1

    merged, added_count = merge_db_into_employees(employees, db_experts)
    print(f"📊 БД: {len(db_experts)} экспертов")
    print(f"📋 employees.json: {len(employees)} → {len(merged)} (+{added_count} новых)")

    if added_count == 0:
        print("✅ employees.json уже актуален")
        return 0

    if args.dry_run:
        print("\n[DRY-RUN] Будет добавлено:")
        by_name = {e["name"]: e for e in employees}
        for ex in sorted(
            [e for e in db_experts if e["name"] not in by_name],
            key=lambda x: x["name"]
        ):
            print(f"  + {ex['name']} ({ex['role']}) — {ex['department']}")
        return 0

    meta["updated"] = datetime.now().strftime("%Y-%m-%d")
    meta["_comment"] = "Единый источник. sync_employees_from_db.py подтягивает экспертов из БД."
    out = {**meta, "employees": merged}
    with open(EMPLOYEES_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ employees.json обновлён (+{added_count})")

    # Запускаем sync_employees для обновления seed, known_names, employees.md
    sync_script = REPO_ROOT / "scripts" / "sync_employees.py"
    if sync_script.exists():
        print("🔄 Запускаю sync_employees.py...")
        rc = os.system(f"{sys.executable} {sync_script}")
        if rc != 0:
            print("⚠️ sync_employees.py завершился с ошибкой")
        else:
            print("✅ sync_employees.py выполнен")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
