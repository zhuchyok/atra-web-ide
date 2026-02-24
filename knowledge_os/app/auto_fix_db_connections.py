"""
Автоматическое исправление проблем с подключениями к БД
Исправляет ошибку "too many clients already"
"""

import asyncio
import os
from datetime import datetime

import asyncpg

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


async def check_and_fix_connections():
    """Проверяет и исправляет проблемы с подключениями"""
    try:
        # Подключаемся для проверки
        conn = await asyncpg.connect(DB_URL, command_timeout=10)
        try:
            # Проверяем количество активных соединений
            stats = await conn.fetchrow("""
                SELECT
                    count(*) as total,
                    count(*) FILTER (WHERE state = 'idle') as idle,
                    count(*) FILTER (WHERE state = 'active') as active,
                    (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max_conn
                FROM pg_stat_activity
                WHERE datname = 'knowledge_os'
            """)

            total = stats["total"]
            idle = stats["idle"]
            active = stats["active"]
            max_conn = stats["max_conn"]

            usage_percent = (total / max_conn) * 100

            print(
                f"[{datetime.now()}] 📊 DB Connections: {total}/{max_conn} ({usage_percent:.1f}%)"
            )
            print(f"   Active: {active}, Idle: {idle}")

            # Если использование > 80%, закрываем старые idle соединения
            if usage_percent > 80:
                print(
                    f"[{datetime.now()}] ⚠️ High connection usage ({usage_percent:.1f}%), cleaning idle connections..."
                )

                # Закрываем idle соединения старше 5 минут
                closed = await conn.execute("""
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = 'knowledge_os'
                    AND state = 'idle'
                    AND state_change < NOW() - INTERVAL '5 minutes'
                    AND pid != pg_backend_pid()
                """)

                print(f"[{datetime.now()}] ✅ Closed old idle connections")
                return True

            return False

        finally:
            await conn.close()

    except asyncpg.exceptions.TooManyConnectionsError:
        print(f"[{datetime.now()}] ❌ Too many connections! Attempting emergency cleanup...")
        # Пытаемся подключиться через другой способ для экстренной очистки
        try:
            # Используем системный пользователь для принудительного закрытия
            admin_conn = await asyncpg.connect(
                DB_URL.replace("admin:secret", "postgres:postgres"), command_timeout=5
            )
            try:
                await admin_conn.execute("""
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = 'knowledge_os'
                    AND state = 'idle'
                    AND pid != pg_backend_pid()
                """)
                print(f"[{datetime.now()}] ✅ Emergency cleanup completed")
            finally:
                await admin_conn.close()
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Emergency cleanup failed: {e}")
        return True

    except Exception as e:
        print(f"[{datetime.now()}] ❌ Connection check error: {e}")
        return False


async def main():
    """Периодическая проверка и исправление"""
    print(f"[{datetime.now()}] 🔧 Auto-fix DB connections started...")

    while True:
        try:
            await check_and_fix_connections()
            await asyncio.sleep(60)  # Проверяем каждую минуту
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Error in auto-fix loop: {e}")
            await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
