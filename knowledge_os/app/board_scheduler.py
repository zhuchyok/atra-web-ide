import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

# Add paths (в Docker: PYTHONPATH=/app/knowledge_os/app уже задан в compose)
sys.path.insert(0, "/app")
sys.path.insert(0, "/app/knowledge_os/app")

from strategic_board import run_board_meeting

# Setup logging: в Docker при монтировании :ro /app/logs недоступен — пишем в /tmp
log_dir = "/app/logs" if os.access("/app", os.W_OK) else "/tmp"
log_file = os.path.join(log_dir, "board_scheduler.log")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("board_scheduler")


def get_msk_now():
    return datetime.now(timezone(timedelta(hours=3)))


async def main():
    interval = 6 * 3600  # 6 hours
    logger.info(f"🚀 Board Scheduler started. Interval: 6 hours. Current MSK time: {get_msk_now()}")

    while True:
        try:
            logger.info(f"🏛 Starting scheduled Board Meeting at {get_msk_now()} MSK...")
            await run_board_meeting()
            logger.info(
                f"✅ Board Meeting finished. Next run in 6 hours. Next MSK run: {get_msk_now() + timedelta(seconds=interval)}"
            )
        except Exception as e:
            logger.error(f"❌ Error in Board Meeting: {e}")

        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(main())
