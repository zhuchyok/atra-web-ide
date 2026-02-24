#!/usr/bin/env python3
"""Запуск оптимизации с выводом прогресса в реальном времени"""

import os
import subprocess
import sys
import time


def main():
    print("🚀 ЗАПУСК ОПТИМИЗАЦИИ С ПРОГРЕССОМ")
    print("=" * 70)
    print()

    # Запускаем оптимизацию
    script_path = os.path.join(os.path.dirname(__file__), "optimize_symbol_params_with_ai.py")

    process = subprocess.Popen(
        [sys.executable, script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,
    )

    # Выводим вывод в реальном времени
    for line in process.stdout:
        print(line, end="")
        sys.stdout.flush()

    process.wait()
    print(f"\n✅ Оптимизация завершена с кодом: {process.returncode}")


if __name__ == "__main__":
    main()
