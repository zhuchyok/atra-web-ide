"""
Автоматическое исправление проблем с подключениями к БД.
Исправляет ошибку "too many clients already".

Best practices (2026):
- При старте сервисов после Docker restart — все пулы открываются одновременно,
  суммарно превышая max_connections. idle_in_transaction_session_timeout=300s в Postgres
  теперь убивает их автоматически, но этот модуль — дополнительный уровень защиты.
- Чистим idle соединения при >70% (было 80% — слишком поздно).
- При TooManyConnectionsError — экстренная чистка через superuser слот
  (PostgreSQL резервирует superuser_reserved_connections=3 для таких случаев).
"""

import asyncio
import os
from datetime import datetime

import asyncpg

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
# Superuser URL для экстренной чистки (PostgreSQL резервирует 3 слота для superuser)
_SUPERUSER_URL = DB_URL.replace("admin:secret", "postgres:postgres")


async def check_and_fix_connections():
    """Проверяет и исправляет проблемы с подключениями"""
    try:
        conn = await asyncpg.connect(DB_URL, command_timeout=10)
        try:
            stats = await conn.fetchrow("""
                SELECT
                    count(*) as total,
                    count(*) FILTER (WHERE state = 'idle') as idle,
                    count(*) FILTER (WHERE state = 'active') as active,
                    count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_tx,
                    (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max_conn
                FROM pg_stat_activity
                WHERE datname = 'knowledge_os'
            """)

            total = stats["total"]
            idle = stats["idle"]
            active = stats["active"]
            idle_in_tx = stats["idle_in_tx"]
            max_conn = stats["max_conn"]
            usage_percent = (total / max_conn) * 100

            print(
                f"[{datetime.now()}] 📊 DB: {total}/{max_conn} ({usage_percent:.1f}%) "
                f"active={active} idle={idle} idle_in_tx={idle_in_tx}"
            )

            # Порог снижен с 80% до 70% — действуем превентивно
            if usage_percent > 70:
                print(
                    f"[{datetime.now()}] ⚠️ High usage ({usage_percent:.1f}%), cleaning idle connections..."
                )

                # Убиваем idle соединения старше 2 минут (было 5 мин)
                await conn.execute("""
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = 'knowledge_os'
                    AND state = 'idle'
                    AND state_change < NOW() - INTERVAL '2 minutes'
                    AND pid != pg_backend_pid()
                """)

                # Убиваем idle in transaction старше 5 минут
                await conn.execute("""
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = 'knowledge_os'
                    AND state = 'idle in transaction'
                    AND state_change < NOW() - INTERVAL '5 minutes'
                    AND pid != pg_backend_pid()
                """)

                print(f"[{datetime.now()}] ✅ Cleaned idle/idle_in_tx connections")
                return True

            return False

        finally:
            await conn.close()

    except asyncpg.exceptions.TooManyConnectionsError:
        print(
            f"[{datetime.now()}] ❌ Too many connections! Emergency cleanup via superuser slot..."
        )
        try:
            # PostgreSQL резервирует superuser_reserved_connections=3 слота — именно для таких случаев
            admin_conn = await asyncpg.connect(_SUPERUSER_URL, command_timeout=5)
            try:
                terminated = await admin_conn.fetchval("""
                    SELECT count(pg_terminate_backend(pid))
                    FROM pg_stat_activity
                    WHERE datname = 'knowledge_os'
                    AND state = 'idle'
                    AND pid != pg_backend_pid()
                """)
                print(
                    f"[{datetime.now()}] ✅ Emergency cleanup: terminated {terminated} idle connections"
                )
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
            await asyncio.sleep(60)
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Error in auto-fix loop: {e}")
            await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
