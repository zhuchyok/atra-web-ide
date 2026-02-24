#!/usr/bin/env python3
"""
Быстрая настройка администраторов для сервера ATRA
"""

import sys

from src.database.db import Database


def quick_setup_admins():
    """
    Быстрая настройка администраторов
    """
    try:
        db = Database()

        # Пользователь 556251171 - Супер администратор
        user_data_556 = db.get_user_data(556251171)
        if user_data_556:
            user_data_556.update({"role": "super_admin", "is_admin": True, "is_super_admin": True})
            db.save_user_data(556251171, user_data_556)
            print("✅ Пользователь 556251171 назначен супер администратором")
        else:
            print("❌ Пользователь 556251171 не найден")

        # Пользователь 958930260 - Администратор
        user_data_958 = db.get_user_data(958930260)
        if user_data_958:
            user_data_958.update({"role": "admin", "is_admin": True, "is_super_admin": False})
            db.save_user_data(958930260, user_data_958)
            print("✅ Пользователь 958930260 назначен администратором")
        else:
            print("❌ Пользователь 958930260 не найден")

        print("\n🎉 Настройка администраторов завершена!")

    except Exception as e:
        print(f"❌ Ошибка настройки администраторов: {e}")


def show_admin_status():
    """
    Показывает статус администраторов
    """
    try:
        db = Database()
        admin_ids = db.get_admin_ids()

        print("\n📊 СТАТУС АДМИНИСТРАТОРОВ:")
        print("=" * 40)

        for user_id in admin_ids:
            user_data = db.get_user_data(user_id)
            if user_data:
                role = user_data.get("role", "user")
                is_super = user_data.get("is_super_admin", False)
                deposit = user_data.get("deposit", 0)

                admin_type = "🔥 СУПЕР АДМИН" if is_super else "👑 АДМИН"
                print(f"{admin_type}: {user_id}")
                print(f"   Роль: {role}")
                print(f"   Депозит: {deposit}")
                print()

        if not admin_ids:
            print("❌ Администраторы не найдены")

    except Exception as e:
        print(f"❌ Ошибка получения статуса: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        show_admin_status()
    else:
        print("🔧 БЫСТРАЯ НАСТРОЙКА АДМИНИСТРАТОРОВ ATRA")
        print("=" * 50)
        print("Назначаем роли:")
        print("• 556251171 → Супер администратор")
        print("• 958930260 → Администратор")
        print()

        quick_setup_admins()

        print("\n📋 Для проверки статуса используйте:")
        print("python3 quick_admin_setup.py status")
