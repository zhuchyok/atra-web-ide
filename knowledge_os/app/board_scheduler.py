import asyncio
import os
import sys
import logging
from datetime import datetime, timezone, timedelta

# Add paths
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/knowledge_os/app')

from strategic_board import run_board_meeting

# Setup logging to both stdout and a file
log_file = '/app/logs/board_scheduler.log'
os.makedirs('/app/logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('board_scheduler')

def get_msk_now():
    return datetime.now(timezone(timedelta(hours=3)))

async def main():
    interval = 6 * 3600  # 6 hours
    logger.info(f"🚀 Board Scheduler started. Interval: 6 hours. Current MSK time: {get_msk_now()}")
    
    while True:
        try:
            logger.info(f"🏛 Starting scheduled Board Meeting at {get_msk_now()} MSK...")
            await run_board_meeting()
            logger.info(f"✅ Board Meeting finished. Next run in 6 hours. Next MSK run: {get_msk_now() + timedelta(seconds=interval)}")
        except Exception as e:
            logger.error(f"❌ Error in Board Meeting: {e}")
        
        await asyncio.sleep(interval)

if __name__ == '__main__':
    asyncio.run(main())
