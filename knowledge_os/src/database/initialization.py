"""
Модуль инициализации базы данных для торгового бота ATRA.

Содержит функции для инициализации базы данных, проверки её здоровья
и синхронизации данных пользователей.
"""

import json
import logging
import os
import sys

# from datetime import datetime  # Не используется в этом модуле

# Импорты для работы с базой данных
try:
    from src.database.db import Database

    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

# Импорт для инициализации базы данных
try:
    from src.utils import db_init

    DB_INIT_AVAILABLE = True
except ImportError:
    DB_INIT_AVAILABLE = False

logger = logging.getLogger(__name__)


async def initialize_database_on_startup():
    """Инициализация базы данных при запуске"""
    # 🛡️ ЗАЩИТА: Проверяем здоровье БД перед запуском
    try:
        try:
            from src.monitoring.db_health import auto_fix_database, get_db_health_status
        except ImportError:
            from db_health_monitor import (  # pylint: disable=import-outside-toplevel
                auto_fix_database,
                get_db_health_status,
            )

        logger.info("🔍 Проверка целостности БД перед запуском...")
        health = get_db_health_status()

        if not health["integrity_ok"]:
            logger.warning("⚠️ БД повреждена! Запуск автоматического восстановления...")
            if auto_fix_database():
                logger.info("✅ БД успешно восстановлена!")
            else:
                logger.error("❌ Не удалось восстановить БД автоматически!")
        else:
            logger.info("✅ БД в порядке (%.2f MB)", health["size_mb"])
    except ImportError:
        logger.warning("⚠️ Модуль db_health_monitor недоступен, пропускаем проверку целостности")
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        logger.warning("⚠️ Ошибка проверки целостности БД: %s", e)

    try:
        if not DB_INIT_AVAILABLE:
            logger.warning("⚠️ Модуль db_init недоступен: DatabaseInitializer не найден")
            raise ImportError("DatabaseInitializer не доступен")

        logger.info("🔧 Проверка и инициализация базы данных...")
        initializer = db_init.DatabaseInitializer()

        # Проверяем наличие файла user_data.json
        if not os.path.exists("user_data.json"):
            logger.info("📄 Файл user_data.json не найден, создаем...")
            initializer.create_user_data_file()

        # Пытаемся инициализировать с данными, если не получается - только структуру
        try:
            success = await initializer.initialize_database(with_data=True)
            if not success:
                logger.warning("⚠️ Инициализация с данными не удалась, создаем только структуру...")
                success = await initializer.initialize_database(with_data=False)
        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.warning("⚠️ Ошибка инициализации с данными: %s, создаем только структуру...", e)
            success = await initializer.initialize_database(with_data=False)

        if success:
            logger.info("✅ База данных готова к работе")
        else:
            logger.error("❌ Критическая ошибка инициализации базы данных")
            sys.exit(1)

    except ImportError as e:
        logger.warning("⚠️ Модуль db_init недоступен: %s", e)
        logger.info("🔄 Пытаемся инициализировать базу данных через стандартный механизм...")
        try:
            if DB_AVAILABLE:
                Database()  # Инициализируем базу данных
                logger.info("✅ База данных инициализирована через стандартный механизм")
            else:
                logger.error("❌ Модуль db недоступен, не удается инициализировать базу данных")
                sys.exit(1)
        except (
            ValueError,
            TypeError,
            KeyError,
            RuntimeError,
            OSError,
            ConnectionError,
        ) as db_error:
            logger.error("❌ Ошибка инициализации базы данных: %s", db_error)
            sys.exit(1)
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        logger.error("❌ Неожиданная ошибка инициализации базы данных: %s", e)
        sys.exit(1)


async def sync_user_data_from_json_to_db():
    """
    Синхронизирует данные пользователей из user_data.json в базу данных.
    Поддерживает два формата:
    1. Прямой формат: {"123456": {...}, "789012": {...}}
    2. Вложенный формат: {"users": {"123456": {...}, "789012": {...}}, "settings": {...}}
    """
    try:
        if not DB_AVAILABLE:
            logger.warning("⚠️ Модуль db недоступен, пропускаем синхронизацию")
            return False

        user_data_file = "user_data.json"

        if not os.path.exists(user_data_file):
            logger.warning("⚠️ Файл user_data.json не найден")
            return False

        # Загружаем данные из файла
        with open(user_data_file, encoding="utf-8") as file:
            file_data = json.load(file)

        if not file_data:
            logger.warning("⚠️ Файл user_data.json пуст")
            return False

        # Определяем формат данных и извлекаем пользователей
        if isinstance(file_data, dict):
            # Сначала проверяем, есть ли пользователи на верхнем уровне (прямой формат)
            direct_users = {
                k: v
                for k, v in file_data.items()
                if k not in ["users", "settings"]
                and not k.startswith("trader_")
                and isinstance(v, dict)
                and k.isdigit()
            }

            # Проверяем, есть ли ключ "users" (вложенный формат)
            nested_users = {}
            if "users" in file_data and isinstance(file_data["users"], dict):
                nested_users = {
                    k: v
                    for k, v in file_data["users"].items()
                    if isinstance(v, dict) and k.isdigit()
                }

            # Объединяем оба источника (прямой формат имеет приоритет)
            all_user_data = {**nested_users, **direct_users}

            if nested_users and direct_users:
                logger.info(
                    "📋 Обнаружен смешанный формат: %d вложенных + %d прямых = %d всего",
                    len(nested_users),
                    len(direct_users),
                    len(all_user_data),
                )
            elif nested_users:
                logger.info(
                    "📋 Обнаружен вложенный формат (users): %d пользователей", len(all_user_data)
                )
            elif direct_users:
                logger.info("📋 Обнаружен прямой формат: %d пользователей", len(all_user_data))
        else:
            logger.warning("⚠️ Неожиданный формат файла user_data.json")
            return False

        if not all_user_data:
            logger.warning("⚠️ Нет пользователей для синхронизации в user_data.json")
            return False

        # Подключаемся к базе данных
        db = Database()

        synced_count = 0
        skipped_count = 0

        for user_id, user_data in all_user_data.items():
            # Пропускаем тестовых пользователей и служебные ключи
            if user_id.startswith("trader_") or user_id in ["users", "settings"]:
                skipped_count += 1
                logger.debug("⏭️ Пропускаем служебный ключ: %s", user_id)
                continue

            # Проверяем, является ли user_id числом
            try:
                numeric_user_id = int(user_id)
            except ValueError:
                logger.warning("⚠️ Пропускаем нечисловой ключ: %s", user_id)
                skipped_count += 1
                continue

            # Проверяем, что user_data - словарь
            if not isinstance(user_data, dict):
                logger.warning("⚠️ Пропускаем пользователя %s: данные не являются словарём", user_id)
                skipped_count += 1
                continue

            try:
                # Проверяем, есть ли пользователь в базе данных
                existing_user = db.get_user_data(numeric_user_id)

                if existing_user:
                    # Пользователь уже есть в БД, обновляем данные
                    logger.info("🔄 Обновляем данные пользователя %s в БД", user_id)
                    db.save_user_data(numeric_user_id, user_data)
                else:
                    # Пользователя нет в БД, создаем нового
                    logger.info("➕ Создаем нового пользователя %s в БД", user_id)
                    db.save_user_data(numeric_user_id, user_data)

                synced_count += 1
                logger.debug("✅ Пользователь %s синхронизирован", user_id)

            except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                logger.error("❌ Ошибка синхронизации пользователя %s: %s", user_id, e)
                continue

        logger.info(
            "🎉 Синхронизация завершена: %d пользователей синхронизировано, %d пропущено",
            synced_count,
            skipped_count,
        )
        return synced_count > 0

    except (ValueError, TypeError, KeyError, RuntimeError, OSError, json.JSONDecodeError) as e:
        logger.error("❌ Критическая ошибка синхронизации: %s", e)
        return False
