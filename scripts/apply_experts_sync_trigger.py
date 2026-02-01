#!/usr/bin/env python3
"""Применить миграцию триггера для автосинхронизации experts."""

import asyncio
import os
from pathlib import Path

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
MIGRATION_FILE = Path(__file__).resolve().parent.parent / "knowledge_os" / "db" / "migrations" / "add_experts_sync_trigger.sql"


async def apply_migration():
    try:
        import asyncpg
    except ImportError:
        print("❌ asyncpg не установлен")
        return 1

    if not MIGRATION_FILE.exists():
        print(f"❌ Не найден {MIGRATION_FILE}")
        return 1

    sql = MIGRATION_FILE.read_text(encoding="utf-8")

    try:
        conn = await asyncpg.connect(DB_URL)
        print(f"✅ Подключено к БД")
        
        await conn.execute(sql)
        print(f"✅ Миграция применена: {MIGRATION_FILE.name}")
        
        # Проверяем что триггер создан
        trigger_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_trigger 
                WHERE tgname = 'experts_sync_trigger'
            )
        """)
        if trigger_exists:
            print("✅ Триггер experts_sync_trigger активен")
        else:
            print("⚠️ Триггер не создан")
        
        await conn.close()
        return 0
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(apply_migration()))
