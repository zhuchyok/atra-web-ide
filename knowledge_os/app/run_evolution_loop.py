"""
[SINGULARITY 21.28] Perpetual Evolution Loop Runner.
Запускает один цикл эволюции каждые EVOLUTION_INTERVAL_SEC секунд (по умолчанию 21600 = 6 ч).
"""

import asyncio
import logging
import os
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("evolution_loop")

INTERVAL = int(os.getenv("EVOLUTION_INTERVAL_SEC", "28800"))


async def main():
    from perpetual_evolution import PerpetualEvolution

    engine = PerpetualEvolution()

    while True:
        logger.info("🚀 [EVOLUTION] Запуск цикла эволюции...")
        try:
            result = await engine.run_one_cycle()
            logger.info("✅ [EVOLUTION] Цикл завершён, результат: %s", result)
        except Exception as exc:
            logger.error("⚠️ [EVOLUTION] Ошибка цикла: %s", exc)

        logger.info(
            "😴 [EVOLUTION] Следующий цикл через %d сек (%d ч)...", INTERVAL, INTERVAL // 3600
        )
        await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
