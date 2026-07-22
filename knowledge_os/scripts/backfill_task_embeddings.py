#!/usr/bin/env python3
"""Backfill tasks.embedding for completed tasks (SuccessRetriever / Wisdom tab)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from typing import List, Optional

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_task_embeddings")

DATABASE_URL = os.getenv("POSTGRES_DIRECT_URL") or os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("Set DATABASE_URL or POSTGRES_DIRECT_URL")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_EMBED_MODEL", os.getenv("OLLAMA_MODEL", "nomic-embed-text:latest"))
CONCURRENCY = int(os.getenv("TASK_EMBED_CONCURRENCY", "4"))


async def _embed(client: httpx.AsyncClient, sem: asyncio.Semaphore, text: str) -> Optional[List[float]]:
    async with sem:
        for attempt in range(3):
            try:
                resp = await client.post(
                    f"{OLLAMA_BASE_URL}/api/embeddings",
                    json={"model": OLLAMA_MODEL, "prompt": text[:4000]},
                    timeout=45.0,
                )
                if resp.status_code == 200:
                    return resp.json().get("embedding")
                if resp.status_code == 503:
                    await asyncio.sleep(2**attempt)
                    continue
                logger.error("Ollama %s: %s", resp.status_code, resp.text[:200])
                return None
            except Exception as exc:
                logger.warning("embed attempt %s failed: %s", attempt + 1, exc)
                await asyncio.sleep(1)
    return None


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args()

    logger.info(
        "Backfilling task embeddings model=%s limit=%s url=%s",
        OLLAMA_MODEL,
        args.limit,
        OLLAMA_BASE_URL,
    )
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=4)
    sem = asyncio.Semaphore(CONCURRENCY)
    done = 0
    async with httpx.AsyncClient() as client:
        while done < args.limit:
            batch_n = min(20, args.limit - done)
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, COALESCE(title, '') AS title,
                           COALESCE(description, '') AS description,
                           COALESCE(LEFT(result, 1500), '') AS result
                    FROM tasks
                    WHERE status = 'completed' AND embedding IS NULL
                    ORDER BY updated_at DESC
                    LIMIT $1
                    """,
                    batch_n,
                )
            if not rows:
                logger.info("No more tasks without embedding.")
                break

            texts = [
                f"{r['title']}\n{r['description']}\n{r['result']}".strip() or r["title"] or "task"
                for r in rows
            ]
            embeddings = await asyncio.gather(*[_embed(client, sem, t) for t in texts])
            async with pool.acquire() as conn:
                for row, emb in zip(rows, embeddings):
                    if not emb:
                        continue
                    await conn.execute(
                        "UPDATE tasks SET embedding = $1::vector, updated_at = NOW() WHERE id = $2",
                        str(emb),
                        row["id"],
                    )
                    done += 1
            logger.info("Progress: %s / %s (batch size %s)", done, args.limit, len(rows))
    await pool.close()
    logger.info("Done. Embedded %s tasks.", done)


if __name__ == "__main__":
    asyncio.run(main())
