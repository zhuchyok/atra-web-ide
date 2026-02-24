#!/usr/bin/env python3
"""
Показывает чистый прогресс из лога оптимизации (без escape-последовательностей tqdm)
"""

import os
import re
import sys

LOG_FILE = "/tmp/opt_live_new.log"


def clean_tqdm_line(line):
    """Удаляет escape-последовательности tqdm из строки"""
    # Удаляем escape-последовательности типа [A, [B и т.д.
    line = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", line)
    # Удаляем лишние пробелы
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def extract_progress(line):
    """Извлекает информацию о прогрессе из строки"""
    # Ищем строки с прогрессом
    if "Прогресс:" in line or "%|" in line:
        return clean_tqdm_line(line)
    return None


def main():
    if not os.path.exists(LOG_FILE):
        print(f"❌ Лог файл не найден: {LOG_FILE}")
        return

    print("═══════════════════════════════════════════════════════════")
    print("📊 ЧИСТЫЙ ПРОГРЕСС ОПТИМИЗАЦИИ")
    print("═══════════════════════════════════════════════════════════")
    print()

    # Читаем последние строки лога
    try:
        with open(LOG_FILE, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"❌ Ошибка чтения лога: {e}")
        return

    if not lines:
        print("⏳ Лог пуст")
        return

    print(f"📈 Всего строк в логе: {len(lines)}")
    print()

    # Извлекаем прогресс
    progress_lines = []
    for line in lines:
        cleaned = extract_progress(line)
        if cleaned:
            progress_lines.append(cleaned)

    if progress_lines:
        print("📊 Последние сообщения о прогрессе:")
        print("─" * 55)
        for line in progress_lines[-20:]:  # Последние 20 строк прогресса
            print(line)
    else:
        print("⏳ Прогресс еще не записан в лог")
        print()
        print("📈 Последние строки лога:")
        print("─" * 55)
        for line in lines[-10:]:
            cleaned = clean_tqdm_line(line)
            if cleaned:
                print(cleaned)

    print()
    print("═══════════════════════════════════════════════════════════")


if __name__ == "__main__":
    main()
