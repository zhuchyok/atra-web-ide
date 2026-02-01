#!/usr/bin/env python3
"""
Миграция узлов знаний из СТАРОЙ базы в текущую.

Использование:
  # Старая БД (где тысячи узлов) — укажите хост/порт или полный URL
  SOURCE_DATABASE_URL=postgresql://admin:secret@OLD_HOST:5432/knowledge_os \\
  DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os \\
  python3 scripts/migrate_knowledge_from_source_db.py

  # Или для доступа к другому тому (запустите временный postgres с этим томом на порту 5433):
  SOURCE_DATABASE_URL=postgresql://admin:secret@localhost:5433/knowledge_os \\
  python3 scripts/migrate_knowledge_from_source_db.py
"""
import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "knowledge_os"))

SOURCE_URL = os.getenv("SOURCE_DATABASE_URL")
TARGET_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


async def main():
    if not SOURCE_URL:
        print("Укажите SOURCE_DATABASE_URL — старую базу с тысячами узлов")
        print("Пример: SOURCE_DATABASE_URL=postgresql://admin:secret@host:5432/knowledge_os")
        sys.exit(1)

    import asyncpg

    print("📤 Подключение к источнику (старая БД)...")
    try:
        src = await asyncpg.connect(SOURCE_URL)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

    print("📥 Подключение к целевой БД...")
    try:
        dst = await asyncpg.connect(TARGET_URL)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        await src.close()
        sys.exit(1)

    try:
        count_src = await src.fetchval("SELECT COUNT(*) FROM knowledge_nodes")
        print(f"   В источнике: {count_src} узлов")

        count_dst = await dst.fetchval("SELECT COUNT(*) FROM knowledge_nodes")
        print(f"   В целевой:   {count_dst} узлов")

        # Целевая схема: content, embedding, metadata, confidence_score, created_at, usage_count, is_verified
        # Источник может иметь другую структуру — выбираем только общие колонки
        try:
            rows = await src.fetch("""
                SELECT content, metadata, confidence_score,
                       COALESCE(is_verified, false) as is_verified,
                       COALESCE(usage_count, 0) as usage_count,
                       created_at, embedding
                FROM knowledge_nodes
                ORDER BY created_at
            """)
        except Exception:
            rows = await src.fetch("""
                SELECT content, COALESCE(metadata, '{}') as metadata,
                       COALESCE(confidence_score, 0.5) as confidence_score,
                       false as is_verified, 0 as usage_count, created_at, NULL as embedding
                FROM knowledge_nodes
                ORDER BY created_at
            """)
        print(f"\n🔄 Перенос {len(rows)} узлов...")
        inserted = 0
        for r in rows:
            try:
                emb = r.get("embedding")
                # Целевая схема: vector(768). Источник может быть 384 — не подходит, ставим NULL
                if emb is not None:
                    try:
                        s = str(emb).strip("[]")
                        dim = len(s.split(",")) if s else 0
                        if dim != 768:
                            emb = None
                    except Exception:
                        emb = None
                await dst.execute("""
                    INSERT INTO knowledge_nodes (content, metadata, confidence_score, is_verified, usage_count, created_at, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, r["content"], r["metadata"] or "{}", r["confidence_score"] or 0.5,
                   r["is_verified"] or False, r["usage_count"] or 0, r["created_at"], emb)
                inserted += 1
                if inserted % 100 == 0:
                    print(f"   ... {inserted}")
            except Exception as e:
                if "duplicate" not in str(e).lower():
                    print(f"   ⚠️ Пропуск: {e}")
        print(f"\n✅ Перенесено: {inserted}")
        total = await dst.fetchval("SELECT COUNT(*) FROM knowledge_nodes")
        print(f"   Всего в целевой: {total}")
    finally:
        await src.close()
        await dst.close()


if __name__ == "__main__":
    asyncio.run(main())
