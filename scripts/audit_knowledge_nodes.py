import asyncio
import asyncpg
import os
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("knowledge_audit")

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

async def audit_knowledge():
    try:
        conn = await asyncpg.connect(DB_URL)
        # Получаем последние верифицированные инсайты
        nodes = await conn.fetch("""
            SELECT id, content, metadata
            FROM knowledge_nodes
            WHERE is_verified = true
            ORDER BY created_at DESC
            LIMIT 50
        """)

        print(f"\n--- 📊 KNOWLEDGE NODES AUDIT ({len(nodes)} nodes) ---")

        candidates_for_sop = []

        for n in nodes:
            meta = n['metadata']
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except:
                    meta = {}

            node_type = meta.get("type", "unknown")
            content = n['content']

            print(f"ID: {n['id']} | Type: {node_type} | Content: {content[:80]}...")

            # Ищем кандидатов для SOP (успешные внедрения, фиксы, рефакторинги)
            if node_type in ["evolution_log", "fix_report", "optimization"] or "✅" in content:
                candidates_for_sop.append({
                    "id": n['id'],
                    "content": content,
                    "meta": meta
                })

        print(f"\n--- 💡 SOP CANDIDATES FOUND: {len(candidates_for_sop)} ---")
        for c in candidates_for_sop:
            print(f"- {c['content'][:100]}")

        await conn.close()
        return candidates_for_sop
    except Exception as e:
        logger.error(f"Audit failed: {e}")
        return []

if __name__ == "__main__":
    asyncio.run(audit_knowledge())
