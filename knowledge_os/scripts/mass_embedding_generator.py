import asyncio
import logging
import os
import asyncpg
import httpx
import json
import time
from typing import List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mass_embedding_generator")

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "nomic-embed-text:latest")
BATCH_SIZE = 50
MAX_NODES = 1000  # Limit for one run to avoid overloading

async def get_embedding(client: httpx.AsyncClient, text: str) -> Optional[List[float]]:
    url = f"{OLLAMA_BASE_URL}/api/embeddings"
    try:
        response = await client.post(
            url,
            json={"model": OLLAMA_MODEL, "prompt": text},
            timeout=10.0
        )
        if response.status_code == 200:
            return response.json().get("embedding")
        else:
            logger.error(f"Ollama error {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Embedding request failed: {e}")
    return None

async def process_batch(pool, client: httpx.AsyncClient, nodes: List[asyncpg.Record]):
    tasks = []
    for node in nodes:
        content = node['content'][:2000] # Truncate if too long for embedding
        tasks.append(get_embedding(client, content))
    
    embeddings = await asyncio.gather(*tasks)
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            for node, embedding in zip(nodes, embeddings):
                if embedding:
                    await conn.execute(
                        "UPDATE knowledge_nodes SET embedding = $1::vector WHERE id = $2",
                        str(embedding), node['id']
                    )
    return sum(1 for e in embeddings if e is not None)

async def main():
    logger.info(f"🚀 Starting mass embedding generation (Model: {OLLAMA_MODEL}, Max: {MAX_NODES})")
    
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with httpx.AsyncClient() as client:
        total_processed = 0
        while total_processed < MAX_NODES:
            async with pool.acquire() as conn:
                nodes = await conn.fetch(
                    "SELECT id, content FROM knowledge_nodes WHERE embedding IS NULL LIMIT $1",
                    BATCH_SIZE
                )
            
            if not nodes:
                logger.info("✅ No more nodes without embeddings.")
                break
            
            processed = await process_batch(pool, client, nodes)
            total_processed += len(nodes)
            logger.info(f"📦 Processed batch: {len(nodes)} nodes, {processed} embeddings generated. Total: {total_processed}/{MAX_NODES}")
            
            if total_processed >= MAX_NODES:
                break
                
            # Small delay between batches
            await asyncio.sleep(0.5)

    await pool.close()
    logger.info(f"🏁 Mass embedding generation complete. Total processed: {total_processed}")

if __name__ == "__main__":
    asyncio.run(main())
