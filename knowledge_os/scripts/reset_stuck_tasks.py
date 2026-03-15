#!/usr/bin/env python3
"""
Скрипт для возврата зависших задач в pending для повторной обработки.
Запускается периодически через cron.
"""

import asyncio
import os
import sys
from datetime import datetime

import asyncpg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


async def reset_stuck_tasks():
    """Возвращает зависшие задачи в pending"""
    conn = await asyncpg.connect(DB_URL)
    try:
        # Возвращаем задачи, которые зависли в in_progress более 4 часов
        result = await conn.execute("""
            UPDATE tasks
            SET status = 'failed',
                updated_at = NOW(),
                result = 'Terminated by watchdog: stuck in in_progress for > 4 hours',
                metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                    'stuck_reset', true,
                    'stuck_reset_at', NOW()::text,
                    'previous_status', 'in_progress',
                    'reset_count', COALESCE((metadata->>'reset_count')::int, 0) + 1
                )
            WHERE status = 'in_progress'
            AND updated_at < NOW() - INTERVAL '4 hours'
        """)

        reset_count = int(result.split()[-1])

        if reset_count > 0:
            print(f"[{datetime.now()}] ⚠️ Завершено зависших задач (>4ч): {reset_count}")
        else:
            print(f"[{datetime.now()}] ✅ Критически зависших задач (>4ч) не найдено")

        # Дополнительно: возвращаем в pending задачи, которые висят от 1 до 4 часов (мягкий сброс)
        soft_result = await conn.execute("""
            UPDATE tasks
            SET status = 'pending',
                updated_at = NOW(),
                metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                    'soft_reset', true,
                    'soft_reset_at', NOW()::text
                )
            WHERE status = 'in_progress'
            AND updated_at < NOW() - INTERVAL '1 hour'
            AND updated_at >= NOW() - INTERVAL '4 hours'
        """)
        soft_reset_count = int(soft_result.split()[-1])
        if soft_reset_count > 0:
            print(f"[{datetime.now()}] 🔄 Возвращено в pending (1-4ч): {soft_reset_count}")

        # Статистика
        stats = await conn.fetch("""
            SELECT status, COUNT(*) as cnt
            FROM tasks
            GROUP BY status
            ORDER BY cnt DESC
        """)

        print(f"[{datetime.now()}] 📊 Статистика задач:")
        for row in stats:
            print(f"   {row['status']}: {row['cnt']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(reset_stuck_tasks())
