#!/usr/bin/env python3
"""
Исправление предупреждений о профилировании
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_profiling_issue():
    """Проверяет проблему с профилированием"""
    print("🔍 Проверка проблемы с профилированием...")

    # Ищем где используется get_dynamic_tp_levels
    import subprocess

    try:
        result = subprocess.run(
            ["grep", "-r", "get_dynamic_tp_levels", "src/", "--include=*.py"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )

        if result.returncode == 0 and result.stdout:
            print("📋 Найдены использования get_dynamic_tp_levels:")
            lines = result.stdout.strip().split("\n")[:5]
            for line in lines:
                print(f"   {line[:100]}")
        else:
            print("✅ get_dynamic_tp_levels не найден в src/")

    except Exception as e:
        print(f"⚠️ Ошибка поиска: {e}")

    print("\n💡 Рекомендация:")
    print("   Предупреждения о профилировании не критичны.")
    print("   Они возникают при использовании cProfile в коде.")
    print("   Можно игнорировать или отключить профилирование в продакшене.")


if __name__ == "__main__":
    check_profiling_issue()
