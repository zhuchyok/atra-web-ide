#!/usr/bin/env python3
"""
Скрипт для исправления проблем на сервере:
1. Создание таблиц whitelist и blacklist
2. Копирование файлов ИИ-оптимизированных параметров
"""

import json
import os
import shutil
import sqlite3
from pathlib import Path


def create_whitelist_blacklist_tables(db_path: str = "trading.db"):
    """Создает таблицы whitelist и blacklist в базе данных"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Создаем таблицу whitelist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                symbol TEXT PRIMARY KEY,
                market_cap REAL,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        """)

        # Создаем таблицу blacklist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                symbol TEXT PRIMARY KEY,
                market_cap REAL,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        """)

        conn.commit()
        conn.close()
        print(f"✅ Таблицы whitelist и blacklist созданы в {db_path}")
        return True
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")
        return False


def copy_filter_parameters(
    source: str = "ai_learning_data/filter_parameters.json",
    target: str = "ai_learning_data/filter_parameters.json",
):
    """Копирует файл filter_parameters.json"""
    try:
        source_path = Path(source)
        target_path = Path(target)

        if not source_path.exists():
            print(f"⚠️ Исходный файл не найден: {source_path}")
            # Создаем минимальный файл с дефолтными параметрами
            default_params = {
                "quality_thresholds": {
                    "long": {"strict": 0.65, "soft": 0.60},
                    "short": {"strict": 0.65, "soft": 0.60},
                },
                "volume_ratio": {"strict": 1.0, "soft": 0.8},
            }
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(default_params, f, indent=2, ensure_ascii=False)
            print(f"✅ Создан файл с дефолтными параметрами: {target_path}")
            return True

        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        print(f"✅ Файл скопирован: {source_path} -> {target_path}")
        return True
    except Exception as e:
        print(f"❌ Ошибка копирования файла: {e}")
        return False


def copy_optimized_params(source_dir: str = "backtests", target_dir: str = "backtests"):
    """Копирует последний файл оптимизации"""
    try:
        source_path = Path(source_dir)
        target_path = Path(target_dir)

        # Находим последний файл оптимизации
        json_files = sorted(
            source_path.glob("optimize_intelligent_params_*.json"),
            key=os.path.getmtime,
            reverse=True,
        )

        if not json_files:
            print(f"⚠️ Файлы оптимизации не найдены в {source_dir}")
            return False

        latest_file = json_files[0]
        target_path.mkdir(parents=True, exist_ok=True)
        target_file = target_path / latest_file.name

        shutil.copy2(latest_file, target_file)
        print(f"✅ Файл оптимизации скопирован: {latest_file.name} -> {target_file}")
        return True
    except Exception as e:
        print(f"❌ Ошибка копирования файла оптимизации: {e}")
        return False


def create_symbol_params_dir(target_dir: str = "ai_learning_data/symbol_params"):
    """Создает директорию для символ-специфичных параметров"""
    try:
        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Директория создана: {target_path}")
        return True
    except Exception as e:
        print(f"❌ Ошибка создания директории: {e}")
        return False


def main():
    """Основная функция"""
    print("🔧 Начинаем исправление проблем на сервере...")

    # 1. Создаем таблицы whitelist и blacklist
    print("\n1️⃣ Создание таблиц whitelist и blacklist...")
    create_whitelist_blacklist_tables()

    # 2. Копируем filter_parameters.json
    print("\n2️⃣ Копирование filter_parameters.json...")
    copy_filter_parameters()

    # 3. Копируем последний файл оптимизации
    print("\n3️⃣ Копирование файла оптимизации...")
    copy_optimized_params()

    # 4. Создаем директорию для символ-специфичных параметров
    print("\n4️⃣ Создание директории symbol_params...")
    create_symbol_params_dir()

    print("\n✅ Все исправления применены!")


if __name__ == "__main__":
    main()
