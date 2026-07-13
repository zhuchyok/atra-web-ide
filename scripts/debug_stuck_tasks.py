import asyncio
import json
import os
import sys

# Добавляем путь к ядру системы
sys.path.append('/app/knowledge_os/app')
from redis_manager import redis_manager

async def debug_blackboard_stuck():
    client = await redis_manager.get_client()

    # 1. Проверяем все задачи на Blackboard
    all_goals = await client.hgetall("blackboard:goals")
    print(f"--- Blackboard Goals ({len(all_goals)}) ---")

    status_counts = {}
    stuck_tasks = []

    for task_id, raw_data in all_goals.items():
        data = json.loads(raw_data)
        status = data.get("status")
        status_counts[status] = status_counts.get(status, 0) + 1

        if status in ["bidding_open", "unclaimed"]:
            stuck_tasks.append({
                "id": task_id,
                "status": status,
                "goal": data.get("goal")[:50] + "...",
                "timestamp": data.get("timestamp")
            })

    print(f"Status distribution: {status_counts}")

    # 2. Проверяем активные аукционы
    print("\n--- Active Auctions ---")
    keys = await client.keys("blackboard:bids:*")
    print(f"Found {len(keys)} task bid sets")
    for key in keys:
        bids = await client.hgetall(key)
        print(f"Task {key}: {bids}")

    # 3. Проверяем локи
    print("\n--- Active Locks ---")
    locks = await client.keys("blackboard:lock:*")
    print(f"Found {len(locks)} active locks")
    for lock in locks:
        owner = await client.get(lock)
        ttl = await client.ttl(lock)
        print(f"Lock {lock} owned by {owner} (TTL: {ttl}s)")

    # 4. Проверяем наличие воркеров (через стрим)
    print("\n--- Stream Consumers ---")
    try:
        groups = await client.xinfo_groups("stream:expert_tasks")
        for group in groups:
            print(f"Group {group['name']}: consumers={group['consumers']}, pending={group['pending']}")
            consumers = await client.xinfo_consumers("stream:expert_tasks", group['name'])
            for c in consumers:
                print(f"  - Consumer {c['name']}: idle={c['idle']}ms, pending={c['pending']}")
    except Exception as e:
        print(f"Error checking stream: {e}")

if __name__ == "__main__":
    asyncio.run(debug_blackboard_stuck())
