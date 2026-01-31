#!/usr/bin/env python3
"""
Применение HNSW индекса для knowledge_nodes.embedding.
Запуск: PYTHONPATH=backend:. python scripts/apply_hnsw_index.py
"""
import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))


async def main():
    database_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

    try:
        import asyncpg
    except ImportError:
        print("❌ asyncpg не установлен: pip install asyncpg")
        return 1

    try:
        conn = await asyncpg.connect(database_url)
    except Exception as e:
        print(f"❌ Подключение к БД: {e}")
        return 1

    try:
        # Проверяем существующие индексы
        rows = await conn.fetch("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'knowledge_nodes' AND indexdef LIKE '%embedding%'
        """)
        if rows:
            print("Текущие индексы на embedding:")
            for r in rows:
                print(f"  - {r['indexname']}")

        # HNSW не поддерживает CONCURRENTLY в одной транзакции — создаём без него
        await conn.execute("DROP INDEX IF EXISTS knowledge_nodes_embedding_hnsw_idx")
        await conn.execute("""
            CREATE INDEX knowledge_nodes_embedding_hnsw_idx
            ON knowledge_nodes
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """)
        print("✅ HNSW индекс создан: knowledge_nodes_embedding_hnsw_idx")

        # Проверка
        rows = await conn.fetch("""
            SELECT indexname, pg_size_pretty(pg_relation_size(indexname::regclass)) as size
            FROM pg_indexes
            WHERE tablename = 'knowledge_nodes' AND indexdef LIKE '%hnsw%'
        """)
        for r in rows:
            print(f"   Размер: {r['size']}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1
    finally:
        await conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
