#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🔧 АВТОМАТИЧЕСКАЯ ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ATRA
Скрипт для создания и проверки базы данных при первом запуске на сервере
"""

import os
import sys
import logging
import sqlite3
import asyncio
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now
from typing import Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseInitializer:
    """Класс для автоматической инициализации базы данных"""

    def __init__(self, db_path: str = "trading.db"):
        self.db_path = db_path
        self.backup_dir = "backups"

    def check_database_exists(self) -> bool:
        """Проверяет существование файла базы данных"""
        return os.path.exists(self.db_path)

    def check_database_integrity(self) -> bool:
        """Проверяет целостность базы данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()
            conn.close()

            if result and result[0] == "ok":
                logger.info("✅ База данных прошла проверку целостности")
                return True
            else:
                logger.error(f"❌ База данных повреждена: {result[0] if result else 'Неизвестная ошибка'}")
                return False

        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка проверки целостности базы данных: {e}")
            return False

    def check_database_tables(self) -> bool:
        """Проверяет наличие необходимых таблиц в базе данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Список обязательных таблиц
            required_tables = [
                'signals', 'active_signals', 'backtest_results',
                'telemetry_api', 'users_data', 'signals_log',
                'fees', 'quotes', 'arbitrage_events', 'pairs', 'manual_trades'
            ]

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            existing_tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            missing_tables = [table for table in required_tables if table not in existing_tables]

            if missing_tables:
                logger.warning(f"⚠️ Отсутствуют таблицы: {missing_tables}")
                return False
            else:
                logger.info("✅ Все необходимые таблицы присутствуют")
                return True

        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка проверки таблиц: {e}")
            return False

    def create_backup_dir(self):
        """Создает директорию для бэкапов"""
        try:
            os.makedirs(self.backup_dir, exist_ok=True)
            logger.info(f"✅ Директория для бэкапов создана: {self.backup_dir}")
        except OSError as e:
            logger.error(f"❌ Не удалось создать директорию для бэкапов: {e}")

    def backup_corrupted_database(self):
        """Создает бэкап поврежденной базы данных"""
        if not self.check_database_exists():
            return

        try:
            timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(self.backup_dir, f"trading_corrupted_{timestamp}.db")

            import shutil
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"✅ Создан бэкап поврежденной базы данных: {backup_path}")

        except (OSError, IOError) as e:
            logger.error(f"❌ Не удалось создать бэкап: {e}")

    def remove_corrupted_database(self):
        """Удаляет поврежденную базу данных"""
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
                logger.info("✅ Поврежденная база данных удалена")

                # Удаляем также WAL и SHM файлы если они есть
                wal_file = f"{self.db_path}-wal"
                shm_file = f"{self.db_path}-shm"

                for file_path in [wal_file, shm_file]:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"✅ Удален файл: {file_path}")

        except OSError as e:
            logger.error(f"❌ Не удалось удалить поврежденную базу данных: {e}")

    def create_user_data_file(self):
        """Создает файл user_data.json если его нет"""
        user_data_file = "user_data.json"

        if os.path.exists(user_data_file):
            logger.info("✅ Файл user_data.json уже существует")
            return True

        default_user_data = {
            "users": {},
            "settings": {
                "default_filter_mode": "strict",
                "default_trade_mode": "spot",
                "default_risk_pct": 2.0,
                "default_leverage": 1.0
            }
        }

        try:
            import json
            with open(user_data_file, 'w', encoding='utf-8') as f:
                json.dump(default_user_data, f, ensure_ascii=False, indent=2)
            logger.info("✅ Создан файл user_data.json")
            return True
        except IOError as e:
            logger.error(f"❌ Ошибка создания файла user_data.json: {e}")
            return False

    async def initialize_database_with_data(self):
        """Инициализирует базу данных с начальными данными"""
        try:
            logger.info("🔄 Инициализация базы данных с данными...")

            # Создаем файл user_data.json
            self.create_user_data_file()

            # Импортируем необходимые модули
            try:
                from src.database.db import Database
            except ImportError:
                from db import Database
            try:
                from src.execution.exchange_api import BybitAPI, MEXCAPI
            except ImportError:
                from exchange_api import BybitAPI, MEXCAPI

            # Создаем экземпляр базы данных (это автоматически создаст таблицы)
            db = Database(self.db_path)

            # Загружаем пары с бирж
            logger.info("📊 Загрузка торговых пар с бирж...")

            try:
                logger.info("🔄 Загрузка пар с Bybit...")
                bybit_pairs = await BybitAPI.get_liquid_spot_pairs()
                logger.info(f"✅ Bybit: найдено {len(bybit_pairs)} пар")

                if bybit_pairs:
                    db.insert_pairs_for_exchange("Bybit", bybit_pairs)
                    db.insert_fees_for_pairs("Bybit", bybit_pairs,
                                           default_maker_fee=0.001,
                                           default_taker_fee=0.001)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка загрузки пар Bybit: {e}")

            try:
                logger.info("🔄 Загрузка пар с MEXC...")
                mexc_pairs = await MEXCAPI.get_liquid_spot_pairs()
                logger.info(f"✅ MEXC: найдено {len(mexc_pairs)} пар")

                if mexc_pairs:
                    db.insert_pairs_for_exchange("MEXC", mexc_pairs)
                    db.insert_fees_for_pairs("MEXC", mexc_pairs,
                                           default_maker_fee=0.002,
                                           default_taker_fee=0.002)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка загрузки пар MEXC: {e}")

            logger.info("✅ База данных успешно инициализирована с данными")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации базы данных: {e}")
            return False

    def initialize_database_structure_only(self):
        """Создает только структуру базы данных без данных"""
        try:
            logger.info("🔄 Создание структуры базы данных...")

            # Создаем файл user_data.json
            self.create_user_data_file()

            try:
                from src.database.db import Database
            except ImportError:
                from db import Database
            db = Database(self.db_path)

            logger.info("✅ Структура базы данных создана")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка создания структуры базы данных: {e}")
            return False

    async def initialize_database(self, with_data: bool = True) -> bool:
        """Основная функция инициализации базы данных"""
        logger.info("🚀 Начинаем инициализацию базы данных ATRA...")

        # Создаем директорию для бэкапов
        self.create_backup_dir()

        # Проверяем существование базы данных
        if self.check_database_exists():
            logger.info("📁 База данных существует, проверяем целостность...")

            # Проверяем целостность
            if not self.check_database_integrity():
                logger.warning("⚠️ База данных повреждена, создаем бэкап и пересоздаем...")
                self.backup_corrupted_database()
                self.remove_corrupted_database()

                # Создаем новую базу данных
                if with_data:
                    return await self.initialize_database_with_data()
                else:
                    return self.initialize_database_structure_only()

            # Проверяем таблицы
            if not self.check_database_tables():
                logger.warning("⚠️ В базе данных отсутствуют необходимые таблицы, создаем недостающие...")
                # ВМЕСТО ПЕРЕСОЗДАНИЯ БД - создаем недостающие таблицы
                try:
                    from src.database.db import Database
                    db = Database(self.db_path)
                    # _init_tables() создаст только отсутствующие таблицы (CREATE TABLE IF NOT EXISTS)
                    db._init_tables()
                    logger.info("✅ Недостающие таблицы созданы")
                except Exception as e:
                    logger.error("❌ Ошибка создания недостающих таблиц: %s, пытаемся пересоздать БД...", e)
                    # Фолбэк: только если не удалось создать таблицы
                    self.backup_corrupted_database()
                    self.remove_corrupted_database()
                    if with_data:
                        return await self.initialize_database_with_data()
                    else:
                        return self.initialize_database_structure_only()

            logger.info("✅ База данных в порядке, инициализация не требуется")
            return True

        else:
            logger.info("📁 База данных не существует, создаем новую...")

            # Создаем новую базу данных
            if with_data:
                return await self.initialize_database_with_data()
            else:
                return self.initialize_database_structure_only()


async def main():
    """Главная функция для запуска инициализации"""
    import argparse

    parser = argparse.ArgumentParser(description='Инициализация базы данных ATRA')
    parser.add_argument('--db-path', default='trading.db',
                       help='Путь к файлу базы данных')
    parser.add_argument('--structure-only', action='store_true',
                       help='Создать только структуру без данных')

    args = parser.parse_args()

    initializer = DatabaseInitializer(args.db_path)

    success = await initializer.initialize_database(with_data=not args.structure_only)

    if success:
        logger.info("🎉 Инициализация базы данных завершена успешно!")
        sys.exit(0)
    else:
        logger.error("💥 Инициализация базы данных завершилась с ошибками!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
