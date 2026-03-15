import asyncio
import os
import httpx
import asyncpg
from typing import List, Optional

async def get_embedding(text: str) -> Optional[List[float]]:
    embed_url = os.getenv("OLLAMA_EMBED_URL", "http://localhost:11434/api/embeddings")
    model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                embed_url, json={"model": model, "prompt": text[:8000], "keep_alive": 0}
            )
            r.raise_for_status()
            return r.json().get("embedding")
    except Exception as e:
        print(f"Embedding failed: {e}")
        return None

async def backfill_task_embeddings():
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    conn = await asyncpg.connect(db_url)
    try:
        # Find tasks without embeddings that are completed
        rows = await conn.fetch("""
            SELECT id, goal, title, description
            FROM tasks
            WHERE embedding IS NULL
              AND status = 'completed'
              AND (goal IS NOT NULL OR title IS NOT NULL OR description IS NOT NULL)
            ORDER BY created_at DESC
        """)

        if not rows:
            print("No tasks without embeddings found.")
            return

        print(f"Found {len(rows)} tasks to process.")

        for row in rows:
            task_id = row["id"]
            # Use goal, title or description for embedding
            text = row["goal"] or row["title"] or row["description"]
            if not text:
                continue

            print(f"Processing task {task_id}: {text[:50]}...")
            embedding = await get_embedding(text)

            if embedding:
                await conn.execute(
                    "UPDATE tasks SET embedding = $1::vector WHERE id = $2",
                    str(embedding),
                    task_id
                )
                print(f"Updated task {task_id}.")
            else:
                print(f"Failed to get embedding for task {task_id}.")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(backfill_task_embeddings())
