#!/usr/bin/env python3
"""Простой скрипт для показа прогресса оптимизации"""

import os
import sys
import time

LOG_FILE = "/tmp/opt_realtime.log"


def show_progress():
    """Показывает текущий прогресс из лога"""
    if not os.path.exists(LOG_FILE):
        print("⏳ Ожидание запуска оптимизации...")
        return

    try:
        with open(LOG_FILE, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        if not lines:
            print("⏳ Лог пуст, ожидание данных...")
            return

        print("═══════════════════════════════════════════════════════════")
        print("📊 ПРОГРЕСС ОПТИМИЗАЦИИ")
        print("═══════════════════════════════════════════════════════════")
        print()

        # Ищем важные строки
        important = []
        for line in lines:
            line_lower = line.lower()
            if any(
                kw in line_lower
                for kw in [
                    "прогресс",
                    "завершен",
                    "символ",
                    "ethusdt",
                    "bnbusdt",
                    "solusdt",
                    "adausdt",
                    "оптимизация",
                    "лучшие параметры",
                    "сохранение",
                    "error",
                    "exception",
                    "tp_mult",
                    "sl_mult",
                    "✅",
                    "❌",
                    "score",
                    "trades",
                    "win rate",
                ]
            ):
                important.append(line.rstrip())

        if important:
            print("📈 Важные события:")
            for line in important[-20:]:  # Последние 20 важных строк
                print(f"   {line}")
        else:
            print("📈 Последние строки лога:")
            for line in lines[-15:]:
                print(f"   {line.rstrip()}")

        print()
        print("═══════════════════════════════════════════════════════════")
        print(f"⏱️  Обновлено: {time.strftime('%H:%M:%S')}")
        print(f"📊 Всего строк в логе: {len(lines)}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    show_progress()
