import asyncpg
import asyncio
import os

async def main():
    db_url = "postgresql://admin:secret@localhost:5432/knowledge_os"
    conn = await asyncpg.connect(db_url)
    rows = await conn.fetch("SELECT content, metadata FROM knowledge_nodes kn JOIN domains d ON d.id = kn.domain_id WHERE d.name = 'curator_standards'")
    for r in rows:
        print(f"--- CONTENT ---\n{r[0]}\n--- METADATA ---\n{r[1]}\n")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
