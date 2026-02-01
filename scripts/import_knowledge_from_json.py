#!/usr/bin/env python3
"""
Импорт knowledge_nodes из JSON (экспорт с Mac Studio).

  DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os \
  python3 scripts/import_knowledge_from_json.py

Или в Docker:
  docker cp knowledge_nodes_export.json atra-web-ide-backend:/tmp/
  docker exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os \
    atra-web-ide-backend python3 /tmp/import_knowledge_from_json.py
  (предварительно скопировать скрипт в контейнер или смонтировать)
"""
import asyncio
import json
import os
import sys

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
INPUT = os.getenv("INPUT", os.getenv("OUTPUT", "knowledge_nodes_export.json"))


async def main():
    try:
        import asyncpg
    except ImportError:
        print("pip install asyncpg")
        sys.exit(1)

    if not os.path.exists(INPUT):
        print(f"Файл не найден: {INPUT}")
        sys.exit(1)

    with open(INPUT, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"📥 Импорт {len(data)} узлов в", DB_URL.split("@")[-1])
    conn = await asyncpg.connect(DB_URL)

    inserted = 0
    for r in data:
        try:
            meta = r.get("metadata", {})
            if isinstance(meta, dict):
                meta = json.dumps(meta)
            await conn.execute("""
                INSERT INTO knowledge_nodes (content, metadata, confidence_score, is_verified, usage_count, created_at)
                VALUES ($1, $2::jsonb, $3, $4, $5, COALESCE($6::timestamptz, NOW()))
            """,
                r.get("content", ""),
                meta,
                float(r.get("confidence_score", 0.5)),
                bool(r.get("is_verified", False)),
                int(r.get("usage_count", 0)),
                r.get("created_at") or None,
            )
            inserted += 1
            if inserted % 500 == 0:
                print(f"   ... {inserted}")
        except Exception as e:
            if "duplicate" not in str(e).lower():
                print(f"   ⚠️ {e}")

    total = await conn.fetchval("SELECT COUNT(*) FROM knowledge_nodes")
    await conn.close()
    print(f"✅ Импортировано: {inserted}, всего в БД: {total}")


if __name__ == "__main__":
    asyncio.run(main())
