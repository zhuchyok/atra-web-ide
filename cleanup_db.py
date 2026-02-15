import asyncpg
import asyncio
import os

async def main():
    db_url = "postgresql://admin:secret@localhost:5432/knowledge_os"
    conn = await asyncpg.connect(db_url)
    
    # 1. Найти ID домена curator_standards
    domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = 'curator_standards'")
    if not domain_id:
        print("Домен curator_standards не найден.")
        return

    # 2. Удалить все узлы в этом домене, чтобы начать с чистого листа
    deleted = await conn.execute("DELETE FROM knowledge_nodes WHERE domain_id = $1", domain_id)
    print(f"Удалено узлов: {deleted}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
