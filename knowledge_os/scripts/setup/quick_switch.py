#!/usr/bin/env python3
"""
⚡ БЫСТРОЕ ПЕРЕКЛЮЧЕНИЕ НА ИСПРАВЛЕННУЮ ВЕРСИЮ
Простой скрипт для быстрого переключения
"""

import os
import shutil


def quick_switch():
    """Быстрое переключение на исправленную версию"""
    print("⚡ Быстрое переключение на исправленную версию...")

    try:
        # 1. Создаем резервную копию
        if os.path.exists("signal_live_hybrid.py"):
            shutil.copy("signal_live_hybrid.py", "signal_live_hybrid_old.py")
            print("✅ Создана резервная копия: signal_live_hybrid_old.py")

        # 2. Заменяем на исправленную версию
        if os.path.exists("signal_live_hybrid_fixed.py"):
            shutil.copy("signal_live_hybrid_fixed.py", "signal_live_hybrid.py")
            print("✅ Заменено на исправленную версию")
        else:
            print("❌ Файл signal_live_hybrid_fixed.py не найден")
            return False

        # 3. Проверяем результат
        if os.path.exists("signal_live_hybrid.py"):
            print("✅ Переключение выполнено успешно!")
            print("🚀 Перезапустите систему для применения изменений")
            return True
        else:
            print("❌ Ошибка переключения")
            return False

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


if __name__ == "__main__":
    success = quick_switch()
    if success:
        print("\n🎉 Готово! Система переключена на исправленную версию.")
    else:
        print("\n⚠️ Ошибка переключения. Проверьте файлы.")
