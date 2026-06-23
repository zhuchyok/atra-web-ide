import asyncio
import os

import asyncpg

try:
    from distillation_engine import KnowledgeDistiller
except Exception:
    from app.distillation_engine import KnowledgeDistiller

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os")
TARGET = int(os.getenv("DISTILL_TARGET_NODES", "5000"))

SQL_PENDING = """
SELECT COUNT(*)
FROM knowledge_nodes
WHERE content IS NOT NULL
  AND (metadata->>'distilled' IS NULL OR metadata->>'distilled'='false')
  AND COALESCE(metadata->>'distill_status','pending') != 'failed'
  AND (
      metadata->>'distill_status' IS DISTINCT FROM 'retry'
      OR COALESCE((metadata->>'distill_next_retry_ts')::bigint,0) <= EXTRACT(EPOCH FROM NOW())::bigint
  )
"""


async def get_pending(conn: asyncpg.Connection) -> int:
    return int(await conn.fetchval(SQL_PENDING) or 0)


async def main() -> None:
    conn = await asyncpg.connect(DB_URL)
    start_pending = await get_pending(conn)
    distiller = KnowledgeDistiller()
    done = 0
    cycles = 0
    print(f"START_CLOUD pending={start_pending} target={TARGET}", flush=True)
    while done < TARGET:
        before = await get_pending(conn)
        if before <= 0:
            print("STOP no_pending_left", flush=True)
            break
        await distiller.distill_knowledge_batch()
        after = await get_pending(conn)
        processed = max(0, before - after)
        done += processed
        cycles += 1
        print(
            f"PROGRESS_CLOUD cycles={cycles} processed={done}/{TARGET} before={before} after={after} delta={processed}",
            flush=True,
        )
        if processed == 0:
            print("STOP no_progress_in_cycle", flush=True)
            break

    final_pending = await get_pending(conn)
    print(f"FINAL_CLOUD processed={done} cycles={cycles} pending={final_pending}", flush=True)
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
