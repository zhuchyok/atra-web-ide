import asyncpg
import asyncio
import os
import json

async def main():
    db_url = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
    conn = await asyncpg.connect(db_url)

    # 1. Count Mentorship Notes
    m_count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_nodes WHERE metadata->>'type' = 'mentorship_note'")
    print(f"Mentorship Notes: {m_count}")

    # 2. Count SOPs
    sop_count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_nodes WHERE metadata->>'type' = 'sop_document'")
    print(f"SOPs: {sop_count}")

    # 3. Average Audit Score
    avg_score = await conn.fetchval("SELECT AVG((metadata->>'audit_score')::int) FROM tasks WHERE metadata->>'audit_score' IS NOT NULL")
    print(f"Average Audit Score: {avg_score}")

    # 4. Show latest notes
    notes = await conn.fetch("SELECT content FROM knowledge_nodes WHERE metadata->>'type' = 'mentorship_note' ORDER BY created_at DESC LIMIT 3")
    for n in notes:
        print(f"\nNote: {n['content']}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
