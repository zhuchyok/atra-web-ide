#!/usr/bin/env python3
"""
Симуляция процесса настройки Telegram бота
"""

import json
import os
from datetime import datetime

# Константы
USER_DATA_FILE = "user_data.json"

def simulate_telegram_context():
    """Симулирует контекст Telegram бота"""
    print("🤖 Симуляция контекста Telegram бота")
    print("=" * 50)

    # Создаем симуляцию контекста
    class MockContext:
        def __init__(self):
            self.application = MockApplication()

    class MockApplication:
        def __init__(self):
            self.user_data = {}

    context = MockContext()

    # Симулируем процесс настройки пользователя
    user_id = "test_user_123"

    print(f"👤 Симулируем пользователя {user_id}")
    print()

    # Шаг 1: Инициализация пользователя
    print("📝 Шаг 1: Инициализация пользователя")
    context.application.user_data[user_id] = {}
    user_data = context.application.user_data[user_id]
    print(f"   ✅ Пользователь инициализирован")
    print()

    # Шаг 2: Установка депозита
    print("💰 Шаг 2: Установка депозита")
    user_data["deposit"] = 2000
    user_data["setup_step"] = "deposit"
    print(f"   ✅ Депозит установлен: {user_data['deposit']} USDT")
    print(f"   📊 Данные в памяти: {user_data}")
    print()

    # Шаг 3: Выбор режима торговли
    print("📈 Шаг 3: Выбор режима торговли")
    user_data["trade_mode"] = "futures"
    user_data["leverage"] = 1
    user_data["setup_step"] = "trade_mode"
    print(f"   ✅ Режим торговли: {user_data['trade_mode']}")
    print(f"   📊 Данные в памяти: {user_data}")
    print()

    # Шаг 4: Выбор режима фильтров
    print("🎯 Шаг 4: Выбор режима фильтров")
    user_data["filter_mode"] = "strict"
    user_data["news_filter_mode"] = "conservative"
    user_data["setup_step"] = "filter_mode"
    print(f"   ✅ Режим фильтров: {user_data['filter_mode']}")
    print(f"   📊 Данные в памяти: {user_data}")
    print()

    # Шаг 5: Завершение настройки
    print("✅ Шаг 5: Завершение настройки")
    # Добавляем недостающие параметры
    if "total_risk_amount" not in user_data:
        user_data["total_risk_amount"] = 0
    if "free_deposit" not in user_data:
        user_data["free_deposit"] = user_data.get("deposit", 0)
    if "total_profit" not in user_data:
        user_data["total_profit"] = 0
    if "open_positions" not in user_data:
        user_data["open_positions"] = []
    if "accepted_signals" not in user_data:
        user_data["accepted_signals"] = []
    if "trade_history" not in user_data:
        user_data["trade_history"] = []

    # Удаляем setup_step
    if "setup_step" in user_data:
        del user_data["setup_step"]

    print(f"   ✅ Настройка завершена")
    print(f"   📊 Финальные данные: {user_data}")
    print()

    return context

def test_save_user_data(context):
    """Тестирует функцию save_user_data"""
    print("💾 Тестирование функции save_user_data")
    print("=" * 40)

    # Импортируем функцию из telegram_bot.py
    import sys
    sys.path.append('.')

    try:
        # Создаем временный файл для тестирования
        test_file = "test_user_data.json"

        # Сохраняем оригинальный файл
        original_file = USER_DATA_FILE
        if os.path.exists(original_file):
            backup_file = f"backup_{int(datetime.now().timestamp())}.json"
            import shutil
            shutil.copy(original_file, backup_file)
            print(f"💾 Создана резервная копия: {backup_file}")

        # Временно заменяем файл
        import telegram_bot
        original_user_data_file = telegram_bot.USER_DATA_FILE
        telegram_bot.USER_DATA_FILE = test_file

        # Вызываем функцию сохранения
        telegram_bot.save_user_data(context)

        # Проверяем результат
        if os.path.exists(test_file):
            with open(test_file, 'r') as f:
                saved_data = json.load(f)

            print(f"✅ Данные сохранены в {test_file}")
            print(f"📊 Пользователей в файле: {len(saved_data)}")

            for user_id, user_data in saved_data.items():
                print(f"  👤 {user_id}:")
                print(f"    💰 Депозит: {user_data.get('deposit', 'НЕТ')}")
                print(f"    📈 Режим торговли: {user_data.get('trade_mode', 'НЕТ')}")
                print(f"    🎯 Режим фильтров: {user_data.get('filter_mode', 'НЕТ')}")
                print(f"    📰 Новостные фильтры: {user_data.get('news_filter_mode', 'НЕТ')}")
                if 'setup_step' in user_data:
                    print(f"    ⚠️ setup_step: {user_data['setup_step']}")
                else:
                    print(f"    ✅ setup_step удален")
        else:
            print(f"❌ Файл {test_file} не создан")

        # Восстанавливаем оригинальный файл
        telegram_bot.USER_DATA_FILE = original_user_data_file

        # Удаляем тестовый файл
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"🗑️ Тестовый файл удален")

    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Основная функция"""
    print("🚀 Симуляция процесса настройки Telegram бота")
    print("=" * 60)

    # Симулируем контекст
    context = simulate_telegram_context()

    print("🔍 Анализ данных в памяти:")
    for user_id, user_data in context.application.user_data.items():
        print(f"  👤 {user_id}:")
        print(f"    💰 Депозит: {user_data.get('deposit', 'НЕТ')}")
        print(f"    📈 Режим торговли: {user_data.get('trade_mode', 'НЕТ')}")
        print(f"    🎯 Режим фильтров: {user_data.get('filter_mode', 'НЕТ')}")
        print(f"    📰 Новостные фильтры: {user_data.get('news_filter_mode', 'НЕТ')}")
        if 'setup_step' in user_data:
            print(f"    ⚠️ setup_step: {user_data['setup_step']}")
        else:
            print(f"    ✅ setup_step удален")

    print()

    # Тестируем сохранение
    test_save_user_data(context)

    print("\n🎉 Симуляция завершена!")

if __name__ == "__main__":
    main()
