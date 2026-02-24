#!/usr/bin/env python3
"""
Автоматическая установка зависимостей для Singularity 8.0
"""

import subprocess
import sys


def install_dependencies():
    """Устанавливает все необходимые зависимости"""
    print("📦 Установка зависимостей для Singularity 8.0...\n")

    dependencies = ["httpx", "asyncpg", "aiohttp", "pandas", "scikit-learn", "cryptography"]

    for dep in dependencies:
        print(f"📥 Установка {dep}...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", dep],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"  ✅ {dep} установлен")
        except subprocess.CalledProcessError:
            print(f"  ❌ Ошибка установки {dep}")
            return False

    print("\n✅ Все зависимости установлены!")
    return True


if __name__ == "__main__":
    success = install_dependencies()
    sys.exit(0 if success else 1)
