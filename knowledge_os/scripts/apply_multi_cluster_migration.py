#!/usr/bin/env python3
"""
Применить миграцию Multi-Cluster Autonomy (Singularity 21.24).
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import asyncpg
except ImportError:
    print("❌ asyncpg не установлен.")
    sys.exit(1)

MIGRATION_FILE = (
    Path(__file__).parent.parent / "db" / "migrations" / "20260314_multi_cluster_autonomy.sql"
)
DEFAULT_URL = "postgresql://admin:secret@localhost:5432/knowledge_os"


async def main():
    url = os.getenv("DATABASE_URL", os.getenv("POSTGRES_URL", DEFAULT_URL))
    if not MIGRATION_FILE.exists():
        print(f"❌ Файл миграции не найден: {MIGRATION_FILE}")
        return 1

    sql = MIGRATION_FILE.read_text(encoding="utf-8")
    try:
        conn = await asyncio.wait_for(asyncpg.connect(url), timeout=5.0)
        await conn.execute(sql)
        print("✅ Миграция Multi-Cluster Autonomy успешно применена.")
        await conn.close()
        return 0
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
