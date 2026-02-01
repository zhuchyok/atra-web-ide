#!/usr/bin/env python3
"""
Восстановление узлов знаний из knowledge_nodes_archive.
Архив: 131 узел (knowledge_cleaner перенёс старые неиспользуемые).
Свежие 15 — остались в knowledge_nodes.

Запуск:
  cd knowledge_os && python3 ../scripts/restore_knowledge_from_archive.py
  или: DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os python3 scripts/restore_knowledge_from_archive.py
"""
import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "knowledge_os"))

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


async def restore():
    import asyncpg

    print("📦 Восстановление узлов из архива...")
    conn = await asyncpg.connect(DB_URL)

    # Проверяем архив
    archive_count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_nodes_archive")
    print(f"   В архиве: {archive_count} узлов")

    if archive_count == 0:
        print("   Архив пуст.")
        await conn.close()
        return

    # knowledge_nodes: id, content, embedding, metadata, confidence_score, created_at, usage_count, is_verified
    # archive: id(uuid), domain_id, content, metadata, confidence_score, source_ref, created_at, updated_at, is_verified, usage_count, embedding(384)
    # knowledge_nodes.embedding = vector(768), archive.embedding = vector(384) — несовместимо, оставляем NULL
    # domain_id в knowledge_nodes отсутствует — пропускаем
    rows = await conn.fetch("""
        SELECT content, metadata, confidence_score, is_verified, usage_count, created_at
        FROM knowledge_nodes_archive
        ORDER BY created_at
    """)

    inserted = 0
    for r in rows:
        try:
            await conn.execute("""
                INSERT INTO knowledge_nodes (content, metadata, confidence_score, is_verified, usage_count, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, r["content"], r["metadata"] or "{}", r["confidence_score"] or 0.5, r["is_verified"] or False,
               r["usage_count"] or 0, r["created_at"])
            inserted += 1
        except Exception as e:
            print(f"   ⚠️ Ошибка вставки: {e}")

    print(f"✅ Восстановлено: {inserted} узлов")
    total = await conn.fetchval("SELECT COUNT(*) FROM knowledge_nodes")
    print(f"   Всего в knowledge_nodes: {total}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(restore())
