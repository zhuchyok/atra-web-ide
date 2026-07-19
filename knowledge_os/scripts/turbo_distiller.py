# scripts/turbo_distiller.py
"""
[SINGULARITY 31.5] TURBO DISTILLER AUTO-PILOT.
Runs continuous distillation cycles using DuckDB + LanceDB.
Self-monitors and reports progress.
"""

import asyncio
import logging
import os
import sys
import time

# Add app to path
sys.path.append("/app")
sys.path.append("/app/knowledge_os/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TURBO-DISTILLER")


async def run_turbo_cycle():
    try:
        from distillation_engine import KnowledgeDistiller

        distiller = KnowledgeDistiller()

        cycle_count = 0
        while True:
            cycle_count += 1
            logger.info(f"🚀 [TURBO] Starting cycle #{cycle_count}")

            start_time = time.time()
            await distiller.distill_knowledge_batch()
            elapsed = time.time() - start_time

            logger.info(f"✅ [TURBO] Cycle #{cycle_count} completed in {elapsed:.2f}s")

            # Brief pause to let system breathe and sync buffers
            await asyncio.sleep(2)

    except Exception as e:
        logger.error(f"🚨 [TURBO] Critical failure: {e}")
        # Auto-restart after 10s
        await asyncio.sleep(10)
        os.execv(sys.executable, ["python"] + sys.argv)


if __name__ == "__main__":
    logger.info("🔥 [SINGULARITY v31.5] TURBO DISTILLER INITIALIZED. LET'S FLY.")
    asyncio.run(run_turbo_cycle())
