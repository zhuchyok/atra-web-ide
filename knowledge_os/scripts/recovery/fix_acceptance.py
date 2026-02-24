#!/usr/bin/env python3
"""
Скрипт для принудительной установки signal_acceptance_manager в telegram_handlers
"""

import asyncio
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


async def fix_signal_acceptance_manager():
    """Принудительно устанавливает signal_acceptance_manager в telegram_handlers"""

    print("🔧 ИСПРАВЛЕНИЕ signal_acceptance_manager")
    print("=" * 50)

    try:
        # 1. Инициализируем систему принятия сигналов
        print("\n1️⃣ Инициализация системы принятия сигналов...")
        from signal_live_hybrid_fixed import initialize_signal_acceptance_system

        success = await initialize_signal_acceptance_system()

        if success:
            print("   ✅ Система принятия сигналов инициализирована")

            # 2. Получаем signal_acceptance_manager
            print("\n2️⃣ Получение signal_acceptance_manager...")
            from signal_live_hybrid_fixed import signal_acceptance_manager

            if signal_acceptance_manager:
                print("   ✅ signal_acceptance_manager получен")

                # 3. Устанавливаем в telegram_handlers
                print("\n3️⃣ Установка в telegram_handlers...")
                from telegram_handlers import set_signal_acceptance_manager

                set_signal_acceptance_manager(signal_acceptance_manager)
                print("   ✅ signal_acceptance_manager установлен в telegram_handlers")

                # 4. Проверяем установку
                print("\n4️⃣ Проверка установки...")
                from telegram_handlers import signal_acceptance_manager as sam_check

                if sam_check:
                    print("   ✅ signal_acceptance_manager успешно установлен в telegram_handlers")
                    print("   🎉 КНОПКИ ТЕПЕРЬ ДОЛЖНЫ РАБОТАТЬ!")
                else:
                    print("   ❌ signal_acceptance_manager не установлен в telegram_handlers")
            else:
                print("   ❌ signal_acceptance_manager не получен")
        else:
            print("   ❌ Система принятия сигналов не инициализирована")

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(fix_signal_acceptance_manager())
