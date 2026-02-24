#!/usr/bin/env python3
"""
Полная миграция Knowledge OS с сервера на Mac Studio M4 Max
Мигрирует всех экспертов (40+), знания, домены, задачи и логи
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime
from typing import List, Dict
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
SERVER_IP = "185.177.216.15"
SERVER_DB_URL = f"postgresql://admin:secret@{SERVER_IP}:5432/knowledge_os"
LOCAL_DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

# Таблицы для миграции
TABLES_TO_MIGRATE = [
    "experts",           # Все эксперты (40+)
    "domains",           # Домены знаний
    "knowledge_nodes",   # Все знания
    "expert_learning_logs",  # Логи обучения
    "tasks",             # Задачи
    "interaction_logs",  # Логи взаимодействий
    "okrs",              # OKR
    "anomalies",         # Аномалии
    "simulations",       # Симуляции
    "semantic_ai_cache", # Кэш AI запросов
]


async def check_connection(db_url: str, label: str) -> asyncpg.Connection:
    """Проверка подключения к БД"""
    try:
        logger.info(f"📡 Подключение к {label}: {db_url.replace('secret', '***')}")
        conn = await asyncpg.connect(db_url, timeout=30)
        logger.info(f"✅ Подключено к {label}")
        return conn
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к {label}: {e}")
        raise


async def get_table_columns(conn: asyncpg.Connection, table_name: str) -> List[str]:
    """Получает список колонок таблицы"""
    columns = await conn.fetch(f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = $1
        ORDER BY ordinal_position
    """, table_name)
    return [col['column_name'] for col in columns]


async def get_table_count(conn: asyncpg.Connection, table_name: str) -> int:
    """Получает количество записей в таблице"""
    try:
        count = await conn.fetchval(f"SELECT COUNT(*) FROM {table_name}")
        return count or 0
    except Exception as e:
        logger.warning(f"⚠️  Не удалось получить количество для {table_name}: {e}")
        return 0


async def migrate_table(conn_source: asyncpg.Connection, conn_dest: asyncpg.Connection, table_name: str):
    """Миграция одной таблицы"""
    logger.info(f"\n📦 Миграция таблицы: {table_name}")

    # Проверяем существование таблицы
    exists = await conn_source.fetchval(f"""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = $1
        )
    """, table_name)

    if not exists:
        logger.warning(f"   ⏭️  Таблица {table_name} не существует на источнике, пропускаем")
        return 0, 0

    # Получаем данные
    try:
        rows = await conn_source.fetch(f"SELECT * FROM {table_name}")
        total_count = len(rows)
        logger.info(f"   Найдено записей: {total_count}")

        if total_count == 0:
            logger.info(f"   ⏭️  Пропущено (нет данных)")
            return 0, 0

        # Получаем колонки
        columns = await get_table_columns(conn_source, table_name)

        # Вставляем данные
        inserted = 0
        errors = 0

        for row in rows:
            try:
                # Создаем словарь значений
                values = {col: row[col] for col in columns}

                # Строим запрос INSERT с ON CONFLICT
                placeholders = ', '.join([f'${i+1}' for i in range(len(columns))])
                cols = ', '.join(columns)
                value_list = [values[col] for col in columns]

                # Определяем primary key для ON CONFLICT
                # Для большинства таблиц это 'id'
                conflict_cols = "id" if "id" in columns else columns[0]

                # Строим UPDATE clause для ON CONFLICT
                update_cols = [col for col in columns if col != conflict_cols]
                update_set = ', '.join([f"{col} = EXCLUDED.{col}" for col in update_cols])

                query = f"""
                    INSERT INTO {table_name} ({cols})
                    VALUES ({placeholders})
                    ON CONFLICT ({conflict_cols})
                    DO UPDATE SET {update_set}
                """

                await conn_dest.execute(query, *value_list)
                inserted += 1

            except Exception as e:
                logger.warning(f"   ⚠️  Ошибка при вставке записи: {e}")
                errors += 1
                continue

        logger.info(f"   ✅ Вставлено записей: {inserted}/{total_count} (ошибок: {errors})")
        return inserted, errors

    except Exception as e:
        logger.error(f"   ❌ Ошибка миграции {table_name}: {e}")
        return 0, 0


async def migrate_all():
    """Полная миграция всех данных"""
    logger.info("=" * 70)
    logger.info("🚀 НАЧАЛО МИГРАЦИИ НА MAC STUDIO M4 MAX")
    logger.info("=" * 70)
    logger.info(f"📅 Дата: {datetime.now()}")
    logger.info("")

    # Подключение к серверу
    conn_source = None
    conn_dest = None

    try:
        conn_source = await check_connection(SERVER_DB_URL, "СЕРВЕР")

        # Статистика на сервере
        logger.info("\n📊 СТАТИСТИКА НА СЕРВЕРЕ:")
        for table in TABLES_TO_MIGRATE:
            count = await get_table_count(conn_source, table)
            if count > 0:
                logger.info(f"   {table}: {count} записей")

        # Подключение к локальной БД
        conn_dest = await check_connection(LOCAL_DB_URL, "MAC STUDIO БД")
        logger.info("💡 Убедитесь, что контейнер knowledge-os-db запущен!")

        # Миграция
        logger.info("\n🔄 НАЧАЛО МИГРАЦИИ:")
        logger.info("-" * 70)

        start_time = datetime.now()
        total_inserted = 0
        total_errors = 0

        for table in TABLES_TO_MIGRATE:
            inserted, errors = await migrate_table(conn_source, conn_dest, table)
            total_inserted += inserted
            total_errors += errors

        duration = (datetime.now() - start_time).total_seconds()

        # Статистика после миграции
        logger.info("\n📊 СТАТИСТИКА НА MAC STUDIO:")
        for table in TABLES_TO_MIGRATE:
            count = await get_table_count(conn_dest, table)
            if count > 0:
                logger.info(f"   {table}: {count} записей")

        # Итоги
        logger.info("\n" + "=" * 70)
        logger.info(f"✅ МИГРАЦИЯ ЗАВЕРШЕНА за {duration:.1f} секунд")
        logger.info(f"   Всего перенесено: {total_inserted} записей")
        logger.info(f"   Ошибок: {total_errors}")
        logger.info("=" * 70)

        logger.info("\n📋 Следующие шаги:")
        logger.info("1. Проверьте данные в Grafana: http://localhost:3000")
        logger.info("2. Проверьте агентов: docker-compose ps")
        logger.info("3. Проверьте логи: docker-compose logs -f")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка миграции: {e}")
        sys.exit(1)

    finally:
        if conn_source:
            await conn_source.close()
        if conn_dest:
            await conn_dest.close()


if __name__ == "__main__":
    asyncio.run(migrate_all())
