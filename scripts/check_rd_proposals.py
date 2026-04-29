import asyncio
import json
import os
import sys

# Add path to modules
sys.path.insert(0, os.path.join(os.getcwd(), "knowledge_os/app"))

from services.blackboard_service import get_blackboard_service

async def check():
    bb = get_blackboard_service()
    tasks = await bb.get_unclaimed_tasks()
    rd_tasks = [t for t in tasks if "R&D" in t["goal"]]
    print(json.dumps(rd_tasks, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(check())
