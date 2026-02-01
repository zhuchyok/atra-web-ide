#!/usr/bin/env python3
"""
Экспорт knowledge_nodes в портативный JSON (для переноса между разными схемами).
Запускать НА Mac Studio (где postgres с тысячами узлов).

  DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os \
  python3 scripts/export_knowledge_portable.py

Создаёт knowledge_nodes_export.json. Импорт: scripts/import_knowledge_from_json.py
"""
import asyncio
import json
import os
import sys

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
OUTPUT = os.getenv("OUTPUT", "knowledge_nodes_export.json")


async def main():
    try:
        import asyncpg
    except ImportError:
        print("pip install asyncpg")
        sys.exit(1)

    print("📤 Экспорт из", DB_URL)
    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch("""
        SELECT content, metadata, confidence_score, is_verified, usage_count, created_at
        FROM knowledge_nodes
        ORDER BY created_at
    """)
    data = [
        {
            "content": r["content"],
            "metadata": r["metadata"] or {},
            "confidence_score": float(r["confidence_score"] or 0.5),
            "is_verified": bool(r["is_verified"]),
            "usage_count": int(r["usage_count"] or 0),
            "created_at": str(r["created_at"]) if r["created_at"] else None,
        }
        for r in rows
    ]
    await conn.close()

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=None)

    print(f"✅ Экспорт: {len(data)} узлов → {OUTPUT}")
    print(f"   Импорт: OUTPUT={OUTPUT} python3 scripts/import_knowledge_from_json.py")


if __name__ == "__main__":
    asyncio.run(main())
