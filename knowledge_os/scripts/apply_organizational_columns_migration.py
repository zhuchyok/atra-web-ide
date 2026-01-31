#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Применить только миграцию add_experts_organizational_columns.sql.
Идемпотентно: можно запускать многократно.
Использование:
  cd knowledge_os && .venv/bin/python scripts/apply_organizational_columns_migration.py
  или с DATABASE_URL:
  DATABASE_URL=postgresql://... .venv/bin/python scripts/apply_organizational_columns_migration.py
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import asyncpg
except ImportError:
    print("❌ asyncpg не установлен. Активируйте venv: source .venv/bin/activate && pip install -r requirements.txt")
    sys.exit(1)

MIGRATION_FILE = Path(__file__).parent.parent / "db" / "migrations" / "add_experts_organizational_columns.sql"
DEFAULT_URL = "postgresql://admin:secret@localhost:5432/knowledge_os"


async def main():
    url = os.getenv("DATABASE_URL", os.getenv("POSTGRES_URL", DEFAULT_URL))
    if not MIGRATION_FILE.exists():
        print(f"❌ Файл миграции не найден: {MIGRATION_FILE}")
        return 1
    sql = MIGRATION_FILE.read_text(encoding="utf-8")
    try:
        conn = await asyncio.wait_for(asyncpg.connect(url), timeout=5.0)
    except asyncio.TimeoutError:
        print("❌ Таймаут подключения к PostgreSQL. Убедитесь, что БД запущена (Docker или локально).")
        return 1
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        print("   Укажите DATABASE_URL или запустите PostgreSQL.")
        return 1
    try:
        await conn.execute(sql)
        print("✅ Миграция add_experts_organizational_columns.sql применена.")
        return 0
    except Exception as e:
        print(f"❌ Ошибка применения миграции: {e}")
        return 1
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
