#!/usr/bin/env python3
"""
Удаление старых записей из environmental_traces (Collective Memory).
Предотвращает бесконечный рост таблицы при долгой работе Victoria.

Запуск: вручную или по cron, например раз в сутки:
  cd knowledge_os/scripts && python cleanup_old_traces.py

Переменные окружения:
  DATABASE_URL — подключение к БД (по умолчанию localhost)
  TRACES_RETENTION_DAYS — хранить следы за последние N дней (по умолчанию 90)
"""
import asyncio
import os
import sys
import asyncpg
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
RETENTION_DAYS = int(os.getenv('TRACES_RETENTION_DAYS', '90'))


async def cleanup_old_traces():
    """Удаляет из environmental_traces записи старше RETENTION_DAYS дней."""
    conn = await asyncpg.connect(DB_URL)
    try:
        # Проверяем наличие таблицы
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'environmental_traces'
            )
        """)
        if not exists:
            print(f"[{datetime.now()}] Таблица environmental_traces не найдена, пропуск.")
            return

        result = await conn.execute("""
            DELETE FROM environmental_traces
            WHERE timestamp < NOW() - make_interval(days => $1::int)
        """, RETENTION_DAYS)
        deleted = int(result.split()[-1]) if result and result.startswith("DELETE") else 0

        if deleted > 0:
            print(f"[{datetime.now()}] Удалено старых следов: {deleted} (retention={RETENTION_DAYS} дней)")
        else:
            print(f"[{datetime.now()}] Старых следов не найдено (retention={RETENTION_DAYS} дней)")

        # Краткая статистика
        total = await conn.fetchval("SELECT COUNT(*) FROM environmental_traces")
        print(f"[{datetime.now()}] Всего записей в environmental_traces: {total}")
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(cleanup_old_traces())
