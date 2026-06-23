import asyncio
import json
import logging
import os
import sys

import asyncpg
import lancedb
import pyarrow as pa

sys.path.append("/app/knowledge_os/app")
from lancedb_service import EMBEDDING_DIM, LANCE_DB_PATH, TABLE_NAME

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("LANCEDB-SYNC")

DB_URL = os.getenv(
    "DATABASE_URL", "postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os"
)
CHUNK_SIZE = int(os.getenv("LANCEDB_SYNC_CHUNK_SIZE", "500"))


def _parse_vector(vector_str: str):
    if not vector_str or vector_str == "None":
        return None
    try:
        return [float(x) for x in vector_str.strip("[]").split(",")]
    except Exception:
        return None


async def sync_lancedb():
    conn = await asyncpg.connect(DB_URL)
    os.makedirs(LANCE_DB_PATH, exist_ok=True)
    db = lancedb.connect(LANCE_DB_PATH)
    schema = pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), EMBEDDING_DIM)),
            pa.field("content", pa.string()),
            pa.field("metadata", pa.string()),
            pa.field("confidence_score", pa.float32()),
            pa.field("created_at", pa.string()),
        ]
    )

    total = await conn.fetchval(
        """
        SELECT count(*)
        FROM knowledge_nodes
        WHERE metadata->>'distilled' = 'true'
          AND embedding IS NOT NULL
        """
    )
    logger.info(f"Starting LanceDB sync for {total} distilled nodes.")

    offset = 0
    synced = 0
    skipped = 0
    table = None

    while True:
        rows = await conn.fetch(
            """
            SELECT id::text, content, metadata::text AS metadata_str, confidence_score, created_at, embedding::text AS vector_str
            FROM knowledge_nodes
            WHERE metadata->>'distilled' = 'true'
              AND embedding IS NOT NULL
            ORDER BY created_at ASC
            LIMIT $1 OFFSET $2
            """,
            CHUNK_SIZE,
            offset,
        )
        if not rows:
            break

        batch = []
        for row in rows:
            vector = _parse_vector(row["vector_str"])
            if not vector:
                skipped += 1
                continue
            metadata = {}
            if row["metadata_str"]:
                try:
                    metadata = json.loads(row["metadata_str"])
                except Exception:
                    metadata = {}

            batch.append(
                {
                    "id": row["id"],
                    "vector": vector,
                    "content": row["content"] or "",
                    "metadata": json.dumps(metadata),
                    "confidence_score": float(row["confidence_score"] or 0.95),
                    "created_at": str(row["created_at"]),
                }
            )

        if batch:
            if table is None:
                table = db.create_table(TABLE_NAME, data=batch, schema=schema, mode="overwrite")
            else:
                table.add(batch)
            synced += len(batch)

        offset += CHUNK_SIZE
        logger.info(f"Progress: synced={synced} skipped={skipped} offset={offset}/{total}")

    await conn.close()
    logger.info(f"LanceDB sync completed: synced={synced}, skipped={skipped}, total={total}")


if __name__ == "__main__":
    asyncio.run(sync_lancedb())
