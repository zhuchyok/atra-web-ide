import asyncio
import asyncpg
import os
import json

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

async def update_knowledge_domain():
    conn = await asyncpg.connect(DB_URL)

    # Находим ID домена curator_standards
    domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = 'curator_standards' LIMIT 1")

    if domain_id:
        # Обновляем все узлы, связанные со статусом проекта
        await conn.execute("""
            UPDATE knowledge_nodes
            SET domain_id = $1,
                metadata = metadata || '{"standard": "status_project"}'::jsonb
            WHERE content ILIKE '%Как узнать статус проекта%'
        """, domain_id)
        print("✅ Knowledge node moved to curator_standards domain.")
    else:
        print("❌ Domain curator_standards not found.")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(update_knowledge_domain())
