import asyncio
import json
import os
import sys

# Add knowledge_os/app to sys.path
sys.path.insert(0, "/app/knowledge_os/app")

try:
    from redis_manager import redis_manager
except ImportError:
    from app.redis_manager import redis_manager

async def push():
    task_data = {
        "task_id": "46d1a345-80f8-47ea-9276-ce105b9c1d9e",
        "expert_name": "Виктория",
        "description": "Проведи глубокий аудит всей кодовой базы проекта atra-web-ide. [force_ollama]",
        "category": "system",
        "metadata": {"complex": True, "preferred_source": "ollama"}
    }
    await redis_manager.push_to_stream("expert_tasks", task_data)
    print(f"✅ Task 46d1a345-80f8-47ea-9276-ce105b9c1d9e pushed to expert_tasks stream")

if __name__ == "__main__":
    asyncio.run(push())
