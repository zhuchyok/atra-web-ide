#!/usr/bin/env python3
"""
Скрипт для объединения паттернов из backup файла с текущими паттернами
"""

import json
import logging
import os
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_patterns_safely(file_path, max_patterns=None):
    """Безопасная загрузка паттернов с ограничением памяти"""
    try:
        logger.info(f"Загружаем паттерны из {file_path}")

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        if max_patterns and len(data) > max_patterns:
            logger.warning(f"Файл содержит {len(data)} паттернов, ограничиваем до {max_patterns}")
            data = data[:max_patterns]

        logger.info(f"Загружено {len(data)} паттернов")
        return data

    except Exception as e:
        logger.error(f"Ошибка загрузки файла {file_path}: {e}")
        return []


def merge_patterns(current_file, backup_file, output_file, max_total_patterns=100000):
    """Объединяет паттерны из двух файлов"""

    # Загружаем текущие паттерны
    current_patterns = load_patterns_safely(current_file)
    logger.info(f"Текущие паттерны: {len(current_patterns)}")

    # Загружаем backup паттерны (ограничиваем для безопасности)
    backup_patterns = load_patterns_safely(backup_file, max_patterns=50000)
    logger.info(f"Backup паттерны: {len(backup_patterns)}")

    # Создаем объединенный список
    all_patterns = current_patterns + backup_patterns

    # Ограничиваем общее количество паттернов
    if len(all_patterns) > max_total_patterns:
        logger.warning(
            f"Общее количество паттернов ({len(all_patterns)}) превышает лимит ({max_total_patterns})"
        )
        all_patterns = all_patterns[:max_total_patterns]

    # Удаляем дубликаты по symbol + timestamp + signal_type
    unique_patterns = []
    seen = set()

    for pattern in all_patterns:
        key = (
            pattern.get("symbol", ""),
            pattern.get("timestamp", ""),
            pattern.get("signal_type", ""),
        )

        if key not in seen:
            seen.add(key)
            unique_patterns.append(pattern)

    logger.info(f"После удаления дубликатов: {len(unique_patterns)} паттернов")

    # Сохраняем объединенные паттерны
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(unique_patterns, f, indent=2, ensure_ascii=False)

        logger.info(f"Паттерны успешно сохранены в {output_file}")
        return True

    except Exception as e:
        logger.error(f"Ошибка сохранения файла {output_file}: {e}")
        return False


def main():
    """Основная функция"""

    # Пути к файлам
    try:
        from src.config.patterns import get_patterns_file_path
    except ImportError:
        from patterns_config import get_patterns_file_path
    current_file = get_patterns_file_path("main")
    backup_file = "/Users/zhuchyok/Documents/GITHUB/trading_patterns_backup_20251018_182917.json"
    output_file = get_patterns_file_path("merged")

    logger.info("Начинаем объединение паттернов...")

    # Проверяем существование файлов
    if not os.path.exists(current_file):
        logger.error(f"Текущий файл не найден: {current_file}")
        return False

    if not os.path.exists(backup_file):
        logger.error(f"Backup файл не найден: {backup_file}")
        return False

    # Объединяем паттерны
    success = merge_patterns(current_file, backup_file, output_file)

    if success:
        logger.info("✅ Объединение паттернов завершено успешно!")
        logger.info(f"Результат сохранен в: {output_file}")

        # Показываем статистику
        with open(output_file, encoding="utf-8") as f:
            merged_data = json.load(f)

        logger.info("📊 Итоговая статистика:")
        logger.info(f"   - Всего паттернов: {len(merged_data)}")

        # Статистика по результатам
        results = {}
        for pattern in merged_data:
            result = pattern.get("result", "UNKNOWN")
            results[result] = results.get(result, 0) + 1

        for result, count in results.items():
            logger.info(f"   - {result}: {count}")

        return True
    else:
        logger.error("❌ Ошибка при объединении паттернов")
        return False


if __name__ == "__main__":
    main()
