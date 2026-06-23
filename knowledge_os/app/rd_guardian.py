import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta

from redis_manager import redis_manager
from services.notification_service import get_notification_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RD_Guardian")


async def check_status():
    try:
        client = await redis_manager.get_client()

        # 1. Check RAM (via performance-watchdog logs or system)
        # For simplicity, we'll check the ice_mode
        ice_mode = await client.get("system:ice_mode")
        ice_mode = ice_mode.decode() if ice_mode else "normal"

        # 2. Check Tasks
        goals = await client.hgetall("blackboard:goals")
        active_tasks = []
        for tid, raw in goals.items():
            data = json.loads(raw)
            if data.get("status") == "claimed":
                active_tasks.append(f"👤 {data.get('assignee')}: {data.get('goal')[:40]}...")

        # 3. Check Heartbeats
        heartbeats = await client.keys("blackboard:heartbeat:*")

        # 4. Format Report
        report = (
            f"🛰 [R&D GUARDIAN] Отчет за {datetime.now().strftime('%H:%M')}\n"
            f"-----------------------------------\n"
            f"❄️ Режим: {ice_mode.upper()}\n"
            f"🔥 Активных задач: {len(active_tasks)}\n"
            f"💓 Пульс воркеров: {'OK' if len(heartbeats) >= len(active_tasks) else '⚠️ ВНИМАНИЕ'}\n\n"
            + "\n".join(active_tasks)
        )

        return report
    except Exception as e:
        return f"❌ Ошибка Guardian: {str(e)}"


async def main():
    notifier = get_notification_service()
    cycles = 18  # 3 hours / 10 min

    await notifier.notify(
        "🛡 Guardian запущен",
        "Я буду проверять систему каждые 10 минут в течение 3 часов.",
        priority="info",
    )

    for i in range(cycles):
        logger.info(f"Cycle {i + 1}/18 started")
        report = await check_status()
        await notifier.notify(f"📊 Мониторинг ({i + 1}/18)", report, priority="low")

        if i < cycles - 1:
            await asyncio.sleep(600)  # 10 minutes


if __name__ == "__main__":
    asyncio.run(main())
