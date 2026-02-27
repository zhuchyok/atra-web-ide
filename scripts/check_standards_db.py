import asyncio
import asyncpg
import os

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

async def check_standards():
    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch("""
        SELECT kn.id, kn.content, kn.metadata::text as meta
        FROM knowledge_nodes kn
        JOIN domains d ON d.id = kn.domain_id
        WHERE d.name = 'curator_standards'
    """)
    for r in rows:
        print(f"ID: {r['id']} | Meta: {r['meta']} | Content: {r['content'][:100]}...")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_standards())
