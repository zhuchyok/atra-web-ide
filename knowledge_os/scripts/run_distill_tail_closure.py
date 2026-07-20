#!/usr/bin/env python3
"""Bounded distill drain after tail unlock (failed reset + verify)."""

from __future__ import annotations

import asyncio
import logging
import os
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("distill-tail")


async def main() -> None:
    import asyncpg
    from distillation_engine import KnowledgeDistiller
    from distillation_tail_metrics import get_distill_eligible_now

    db = os.environ["DATABASE_URL"]
    rounds = int(os.getenv("TAIL_DISTILL_ROUNDS", "30"))
    target = int(os.getenv("TAIL_DISTILL_TARGET", "20"))
    pause = float(os.getenv("TAIL_DISTILL_PAUSE_SEC", "1"))
    distiller = KnowledgeDistiller()

    for i in range(1, rounds + 1):
        conn = await asyncpg.connect(db)
        try:
            eligible = await get_distill_eligible_now(conn)
        finally:
            await conn.close()

        log.info("ROUND %s/%s eligible_before=%s target=%s", i, rounds, eligible, target)
        if eligible <= target:
            log.info("STOP target reached eligible=%s", eligible)
            break

        t0 = time.time()
        await distiller.distill_knowledge_batch()
        log.info("ROUND %s done in %.1fs", i, time.time() - t0)
        await asyncio.sleep(pause)

    conn = await asyncpg.connect(db)
    try:
        eligible = await get_distill_eligible_now(conn)
        distilled = await conn.fetchval(
            "SELECT count(*) FROM knowledge_nodes WHERE metadata->>'distilled' IN ('true','True')"
        )
        failed = await conn.fetchval(
            "SELECT count(*) FROM knowledge_nodes WHERE metadata->>'distill_status'='failed'"
        )
    finally:
        await conn.close()
    log.info("FINAL eligible=%s distilled=%s failed=%s", eligible, distilled, failed)


if __name__ == "__main__":
    asyncio.run(main())
