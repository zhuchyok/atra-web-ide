#!/usr/bin/env python3
"""
Скрипт для применения миграций PostgreSQL базы данных
Singularity 8.0: Database Migrations
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

# Добавляем путь к knowledge_os
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    print("❌ asyncpg не установлен. Установите: pip install asyncpg")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# Путь к директории с миграциями
MIGRATIONS_DIR = Path(__file__).parent.parent / "db" / "migrations"

# Получаем URL базы данных из переменных окружения
import getpass

USER_NAME = getpass.getuser()

# Используем тот же логик, что и в ai_core.py
if USER_NAME == "zhuchyok":
    default_url = f"postgresql://{USER_NAME}@localhost:5432/knowledge_os"
else:
    default_url = "postgresql://admin:secret@localhost:5432/knowledge_os"

DB_URL = os.getenv(
    "DATABASE_URL", os.getenv("POSTGRES_URL", os.getenv("DATABASE_URL_LOCAL", default_url))
)


class MigrationApplier:
    """Применяет миграции к базе данных PostgreSQL"""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.migrations_dir = MIGRATIONS_DIR

    async def get_applied_migrations(self, conn) -> List[str]:
        """Получает список примененных миграций"""
        try:
            # Создаем таблицу для отслеживания миграций, если её нет
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id SERIAL PRIMARY KEY,
                    migration_name VARCHAR(255) UNIQUE NOT NULL,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Получаем список примененных миграций
            rows = await conn.fetch(
                "SELECT migration_name FROM schema_migrations ORDER BY applied_at"
            )
            return [row["migration_name"] for row in rows]
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка миграций: {e}")
            return []

    async def mark_migration_applied(self, conn, migration_name: str):
        """Отмечает миграцию как примененную"""
        try:
            await conn.execute(
                """
                INSERT INTO schema_migrations (migration_name, applied_at)
                VALUES ($1, NOW())
                ON CONFLICT (migration_name) DO NOTHING
            """,
                migration_name,
            )
        except Exception as e:
            logger.error(f"❌ Ошибка отметки миграции {migration_name}: {e}")

    async def apply_migration(self, conn, migration_file: Path) -> bool:
        """Применяет одну миграцию"""
        migration_name = migration_file.name

        try:
            # Читаем SQL из файла
            sql_content = migration_file.read_text(encoding="utf-8")

            # Применяем миграцию
            await conn.execute(sql_content)

            # Отмечаем как примененную
            await self.mark_migration_applied(conn, migration_name)

            logger.info(f"✅ Применена миграция: {migration_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка применения миграции {migration_name}: {e}")
            return False

    async def apply_all_migrations(self) -> bool:
        """Применяет все непримененные миграции"""
        if not ASYNCPG_AVAILABLE:
            logger.error("❌ asyncpg не установлен")
            return False

        if not self.migrations_dir.exists():
            logger.error(f"❌ Директория миграций не найдена: {self.migrations_dir}")
            return False

        # Получаем список всех SQL файлов миграций
        migration_files = sorted(self.migrations_dir.glob("*.sql"))

        if not migration_files:
            logger.warning("⚠️ Миграции не найдены")
            return False

        logger.info(f"📁 Найдено {len(migration_files)} миграций")

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Получаем список примененных миграций
                applied_migrations = await self.get_applied_migrations(conn)
                logger.info(f"📋 Уже применено миграций: {len(applied_migrations)}")

                # Применяем непримененные миграции
                applied_count = 0
                failed_count = 0

                for migration_file in migration_files:
                    migration_name = migration_file.name

                    if migration_name in applied_migrations:
                        logger.debug(f"⏭️  Пропущена (уже применена): {migration_name}")
                        continue

                    logger.info(f"🔄 Применение миграции: {migration_name}")
                    if await self.apply_migration(conn, migration_file):
                        applied_count += 1
                    else:
                        failed_count += 1
                        logger.error(f"❌ Не удалось применить миграцию: {migration_name}")

                logger.info(f"✅ Применено новых миграций: {applied_count}")
                if failed_count > 0:
                    logger.warning(f"⚠️ Не удалось применить миграций: {failed_count}")

                return failed_count == 0
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к базе данных: {e}")
            logger.error(
                f"   URL: {DB_URL.replace(DB_URL.split('@')[0].split(':')[-1] if '@' in DB_URL else '', '***')}"
            )
            return False


async def main():
    """Главная функция"""
    logger.info("🚀 Запуск применения миграций PostgreSQL...")
    logger.info(f"📁 Директория миграций: {MIGRATIONS_DIR}")
    logger.info(f"🔗 URL базы данных: {DB_URL.split('@')[-1] if '@' in DB_URL else DB_URL}")

    applier = MigrationApplier(DB_URL)
    success = await applier.apply_all_migrations()

    if success:
        logger.info("✅ Все миграции успешно применены!")
        return 0
    else:
        logger.error("❌ Некоторые миграции не удалось применить")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
