import argparse
import asyncio
import json
import logging
import os
import time
from typing import List, Optional

import asyncpg
import httpx

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mass_embedding_generator")

# Configuration
DATABASE_URL = os.getenv(
    "POSTGRES_DIRECT_URL",
    os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os"),
)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "nomic-embed-text:latest")
BATCH_SIZE = 100
DEFAULT_MAX_NODES = 1000
CONCURRENCY_LIMIT = 5  # Limit parallel requests to Ollama

# Semaphore to control concurrency
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)


async def get_embedding(client: httpx.AsyncClient, text: str) -> Optional[List[float]]:
    url = f"{OLLAMA_BASE_URL}/api/embeddings"
    max_retries = 3

    async with semaphore:
        for attempt in range(max_retries):
            try:
                response = await client.post(
                    url, json={"model": OLLAMA_MODEL, "prompt": text}, timeout=30.0
                )
                if response.status_code == 200:
                    return response.json().get("embedding")
                elif response.status_code == 503:
                    wait_time = 2**attempt
                    logger.warning(
                        f"⚠️ Ollama busy (503), retrying in {wait_time}s... (Attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ Ollama error {response.status_code}: {response.text}")
                    break
            except Exception as e:
                logger.error(f"❌ Embedding request failed: {e}")
                await asyncio.sleep(1)
    return None


async def process_batch(pool, client: httpx.AsyncClient, nodes: List[asyncpg.Record]):
    tasks = []
    for node in nodes:
        content = node["content"][:4000]  # Increased limit for better embeddings
        tasks.append(get_embedding(client, content))

    embeddings = await asyncio.gather(*tasks)

    async with pool.acquire() as conn:
        async with conn.transaction():
            for node, embedding in zip(nodes, embeddings):
                if embedding:
                    await conn.execute(
                        "UPDATE knowledge_nodes SET embedding = $1::vector WHERE id = $2",
                        str(embedding),
                        node["id"],
                    )
    return sum(1 for e in embeddings if e is not None)


async def main():
    parser = argparse.ArgumentParser(description="Mass embedding generator for knowledge nodes.")
    parser.get_default("limit")
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_MAX_NODES, help="Maximum nodes to process"
    )
    args = parser.parse_args()

    max_nodes = args.limit
    logger.info(
        f"🚀 Starting mass embedding generation (Model: {OLLAMA_MODEL}, Max: {max_nodes}, Concurrency: {CONCURRENCY_LIMIT})"
    )

    pool = await asyncpg.create_pool(DATABASE_URL)
    async with httpx.AsyncClient() as client:
        total_processed = 0
        while total_processed < max_nodes:
            batch_to_fetch = min(BATCH_SIZE, max_nodes - total_processed)
            async with pool.acquire() as conn:
                nodes = await conn.fetch(
                    "SELECT id, content FROM knowledge_nodes WHERE embedding IS NULL LIMIT $1",
                    batch_to_fetch,
                )

            if not nodes:
                logger.info("✅ No more nodes without embeddings.")
                break

            processed = await process_batch(pool, client, nodes)
            total_processed += len(nodes)
            logger.info(
                f"📦 Processed batch: {len(nodes)} nodes, {processed} embeddings generated. Total: {total_processed}/{max_nodes}"
            )

            if total_processed >= max_nodes:
                break

            # Small delay between batches to let Ollama breathe
            await asyncio.sleep(0.1)

    await pool.close()
    logger.info(f"🏁 Mass embedding generation complete. Total processed: {total_processed}")


if __name__ == "__main__":
    asyncio.run(main())
