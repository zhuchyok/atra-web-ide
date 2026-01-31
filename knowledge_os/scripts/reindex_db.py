import asyncio
import os
import asyncpg
import httpx

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
VECTOR_CORE_URL = "http://localhost:8001"

async def get_embedding(text: str) -> list:
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{VECTOR_CORE_URL}/encode", json={"text": text}, timeout=60.0)
        response.raise_for_status()
        return response.json()["embedding"]

async def reindex_knowledge():
    print("🚀 Starting global re-indexing of knowledge base via VectorCore...")
    conn = await asyncpg.connect(DB_URL)
    
    # Получаем все узлы без эмбеддингов
    nodes = await conn.fetch("SELECT id, content FROM knowledge_nodes WHERE embedding IS NULL")
    print(f"Found {len(nodes)} nodes to re-index.")
    
    for i, node in enumerate(nodes):
        embedding = await get_embedding(node['content'])
        # Передаем как строку для pgvector
        await conn.execute("UPDATE knowledge_nodes SET embedding = $1 WHERE id = $2", str(embedding), node['id'])
        if (i+1) % 50 == 0:
            print(f"Processed {i+1}/{len(nodes)} nodes...")

            
    await conn.close()
    print("✅ Re-indexing completed successfully.")

if __name__ == '__main__':
    asyncio.run(reindex_knowledge())
