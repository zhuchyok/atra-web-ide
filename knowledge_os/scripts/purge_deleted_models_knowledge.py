#!/usr/bin/env python3
"""
Удаление узлов базы знаний (домен "AI Models") по удалённым моделям.
Запускать после миграции purge_deleted_models_data.sql по желанию.
Использование: DATABASE_URL=... python scripts/purge_deleted_models_knowledge.py
"""
import asyncio
import os
import sys

DELETED_MODEL_NAMES = [
    "deepseek-r1-distill-llama:70b",
    "llama3.3:70b",
    "command-r-plus:104b",
    "qwen2.5-coder:32b",
]


async def main():
    try:
        import asyncpg
    except ImportError:
        print("Требуется asyncpg: pip install asyncpg", file=sys.stderr)
        sys.exit(1)
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Задайте DATABASE_URL", file=sys.stderr)
        sys.exit(1)
    conn = await asyncpg.connect(db_url)
    try:
        domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = $1", "AI Models")
        if not domain_id:
            print("Домен 'AI Models' не найден.")
            return
        total = 0
        for name in DELETED_MODEL_NAMES:
            pattern = f"%Модель: {name}%"
            result = await conn.execute(
                """DELETE FROM knowledge_nodes
                   WHERE domain_id = $1 AND content LIKE $2""",
                domain_id,
                pattern,
            )
            # result is like "DELETE 1"
            n = int(result.split()[-1]) if result.split() else 0
            if n:
                print(f"Удалено узлов для модели {name}: {n}")
                total += n
        print(f"Всего удалено узлов: {total}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
