#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка наличия HNSW-индекса на knowledge_nodes.embedding (RAG_PLUS_ROCKET_SPEED).
Выход: 0 — индекс есть, 1 — нет или ошибка.
Использование: cd knowledge_os && python3 scripts/verify_hnsw_index.py
Зависимости: asyncpg (bash knowledge_os/scripts/setup_knowledge_os.sh или pip install asyncpg).
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import asyncpg
except ImportError:
    _venv = Path(__file__).parent.parent / ".venv" / "bin" / "python3"
    if _venv.exists():
        print("❌ asyncpg не установлен в текущем окружении. Запустите: " + str(_venv) + " " + " ".join(sys.argv))
    else:
        print("❌ asyncpg не установлен. Установите: bash knowledge_os/scripts/setup_knowledge_os.sh или pip install asyncpg")
    sys.exit(1)

DB_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("POSTGRES_URL", os.getenv("DATABASE_URL_LOCAL", "postgresql://admin:secret@localhost:5432/knowledge_os")),
)


async def main() -> int:
    try:
        conn = await asyncpg.connect(DB_URL)
        try:
            rows = await conn.fetch(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'knowledge_nodes'
                  AND indexdef LIKE '%embedding%'
                """
            )
            hnsw = [r for r in rows if "hnsw" in (r["indexdef"] or "").lower()]
            if hnsw:
                print("✅ HNSW индекс на knowledge_nodes.embedding найден:", hnsw[0]["indexname"])
                return 0
            if rows:
                print("⚠️ Найден индекс на embedding, но не HNSW:", [r["indexname"] for r in rows])
            else:
                print("❌ Индекс на knowledge_nodes.embedding не найден. Примените миграции: python scripts/apply_migrations.py")
            return 1
        finally:
            await conn.close()
    except Exception as e:
        print(f"❌ Ошибка проверки: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
