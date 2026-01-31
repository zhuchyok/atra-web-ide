#!/usr/bin/env python3
"""
Скрипт для развертывания ролей администраторов на сервере
Поддерживает локальное развертывание и удаленную отправку
"""

import os
import json
import subprocess
import sys
from datetime import datetime

def create_admin_roles_file():
    """
    Создает файл с ролями администраторов для отправки на сервер
    """
    admin_roles = {
        "556251171": {
            "role": "super_admin",
            "is_admin": True,
            "is_super_admin": True,
            "description": "Супер администратор - полные права"
        },
        "958930260": {
            "role": "admin",
            "is_admin": True,
            "is_super_admin": False,
            "description": "Администратор - ограниченные права"
        }
    }

    # Сохраняем в файл
    with open("admin_roles.json", "w", encoding="utf-8") as f:
        json.dump(admin_roles, f, ensure_ascii=False, indent=2)

    print("✅ Создан файл admin_roles.json с ролями администраторов")
    return admin_roles

def create_server_script():
    """
    Создает скрипт для выполнения на сервере
    """
    server_script = '''#!/usr/bin/env python3
"""
Скрипт для применения ролей администраторов на сервере
Запускать на сервере после получения admin_roles.json
"""

import json
import os
import sys
from src.database.db import Database

def apply_admin_roles():
    """Применяет роли администраторов из файла admin_roles.json"""
    try:
        # Проверяем наличие файла
        if not os.path.exists("admin_roles.json"):
            print("❌ Файл admin_roles.json не найден")
            return False

        # Загружаем роли
        with open("admin_roles.json", "r", encoding="utf-8") as f:
            admin_roles = json.load(f)

        print("🔧 ПРИМЕНЕНИЕ РОЛЕЙ АДМИНИСТРАТОРОВ НА СЕРВЕРЕ")
        print("=" * 50)

        db = Database()
        success_count = 0

        for user_id_str, role_data in admin_roles.items():
            try:
                user_id = int(user_id_str)

                # Получаем текущие данные пользователя
                user_data = db.get_user_data(user_id)
                if not user_data:
                    print(f"❌ Пользователь {user_id} не найден в базе данных")
                    continue

                # Обновляем роль
                user_data.update({
                    "role": role_data["role"],
                    "is_admin": role_data["is_admin"],
                    "is_super_admin": role_data["is_super_admin"]
                })

                # Сохраняем
                if db.save_user_data(user_id, user_data):
                    print(f"✅ {role_data['description']}: {user_id}")
                    success_count += 1
                else:
                    print(f"❌ Ошибка сохранения для пользователя {user_id}")

            except Exception as e:
                print(f"❌ Ошибка обработки пользователя {user_id_str}: {e}")

        print(f"\\n🎉 Применено ролей: {success_count}/{len(admin_roles)}")

        # Проверяем результат
        print("\\n📊 ПРОВЕРКА РЕЗУЛЬТАТА:")
        admin_ids = db.get_admin_ids()
        for admin_id in admin_ids:
            admin_data = db.get_user_data(admin_id)
            if admin_data:
                role = admin_data.get("role", "user")
                is_super = admin_data.get("is_super_admin", False)
                admin_type = "🔥 СУПЕР АДМИН" if is_super else "👑 АДМИН"
                print(f"{admin_type}: {admin_id} ({role})")

        return success_count == len(admin_roles)

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        return False

if __name__ == "__main__":
    apply_admin_roles()
'''

    with open("apply_admin_roles_server.py", "w", encoding="utf-8") as f:
        f.write(server_script)

    print("✅ Создан скрипт apply_admin_roles_server.py для сервера")

def create_deployment_script():
    """
    Создает скрипт для автоматического развертывания
    """
    deployment_script = '''#!/bin/bash
# Скрипт для развертывания ролей администраторов на сервере

echo "🚀 РАЗВЕРТЫВАНИЕ РОЛЕЙ АДМИНИСТРАТОРОВ НА СЕРВЕРЕ"
echo "================================================"

# Проверяем наличие файлов
if [ ! -f "admin_roles.json" ]; then
    echo "❌ Файл admin_roles.json не найден"
    exit 1
fi

if [ ! -f "apply_admin_roles_server.py" ]; then
    echo "❌ Файл apply_admin_roles_server.py не найден"
    exit 1
fi

# Создаем бэкап базы данных
echo "📦 Создание бэкапа базы данных..."
cp trading.db backups/trading_backup_$(date +%Y%m%d_%H%M%S).db

# Применяем роли
echo "🔧 Применение ролей администраторов..."
python3 apply_admin_roles_server.py

# Проверяем результат
if [ $? -eq 0 ]; then
    echo "✅ Роли администраторов успешно применены!"
else
    echo "❌ Ошибка применения ролей"
    exit 1
fi

echo "🎉 Развертывание завершено!"
'''

    with open("deploy_admin_roles.sh", "w", encoding="utf-8") as f:
        f.write(deployment_script)

    # Делаем скрипт исполняемым
    os.chmod("deploy_admin_roles.sh", 0o755)

    print("✅ Создан скрипт deploy_admin_roles.sh для развертывания")

def send_to_server_via_scp(server_info):
    """
    Отправляет файлы на сервер через SCP
    """
    try:
        files_to_send = [
            "admin_roles.json",
            "apply_admin_roles_server.py",
            "deploy_admin_roles.sh",
            "fix_missing_admin.py"
        ]

        print(f"📤 Отправка файлов на сервер {server_info['host']}...")

        for file in files_to_send:
            if os.path.exists(file):
                cmd = [
                    "scp", file,
                    f"{server_info['user']}@{server_info['host']}:{server_info['path']}/"
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"✅ {file} отправлен")
                else:
                    print(f"❌ Ошибка отправки {file}: {result.stderr}")
                    return False
            else:
                print(f"⚠️ Файл {file} не найден")

        return True

    except Exception as e:
        print(f"❌ Ошибка отправки на сервер: {e}")
        return False

def execute_on_server_via_ssh(server_info):
    """
    Выполняет команды на сервере через SSH
    """
    try:
        print(f"🔧 Выполнение команд на сервере {server_info['host']}...")

        commands = [
            f"cd {server_info['path']}",
            "chmod +x deploy_admin_roles.sh",
            "./deploy_admin_roles.sh"
        ]

        cmd = [
            "ssh", f"{server_info['user']}@{server_info['host']}",
            " && ".join(commands)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Команды успешно выполнены на сервере")
            print(result.stdout)
            return True
        else:
            print(f"❌ Ошибка выполнения команд: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Ошибка выполнения на сервере: {e}")
        return False

def main():
    """
    Основная функция
    """
    print("🚀 РАЗВЕРТЫВАНИЕ РОЛЕЙ АДМИНИСТРАТОРОВ")
    print("=" * 50)

    # Создаем необходимые файлы
    create_admin_roles_file()
    create_server_script()
    create_deployment_script()

    print("\n📋 СОЗДАННЫЕ ФАЙЛЫ:")
    print("• admin_roles.json - роли администраторов")
    print("• apply_admin_roles_server.py - скрипт для сервера")
    print("• deploy_admin_roles.sh - скрипт развертывания")

    print("\n🎯 ВАРИАНТЫ РАЗВЕРТЫВАНИЯ:")
    print("1. Ручная отправка файлов на сервер")
    print("2. Автоматическая отправка через SCP/SSH")
    print("3. Локальное применение (если запускаете на сервере)")

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "local":
            # Локальное применение (на сервере)
            print("\n🔧 Локальное применение ролей...")
            try:
                from apply_admin_roles_server import apply_admin_roles
                if apply_admin_roles():
                    print("✅ Роли применены локально")
                else:
                    print("❌ Ошибка применения ролей")
            except ImportError:
                print("❌ Файл apply_admin_roles_server.py не найден")

        elif command == "deploy" and len(sys.argv) >= 5:
            # Автоматическое развертывание
            server_info = {
                "user": sys.argv[2],
                "host": sys.argv[3],
                "path": sys.argv[4]
            }

            print(f"\n📤 Автоматическое развертывание на {server_info['host']}...")

            if send_to_server_via_scp(server_info):
                if execute_on_server_via_ssh(server_info):
                    print("🎉 Развертывание завершено успешно!")
                else:
                    print("❌ Ошибка выполнения на сервере")
            else:
                print("❌ Ошибка отправки файлов")

        else:
            print("\n❌ Неверная команда или параметры")
            print("Использование:")
            print("  python3 deploy_admin_roles.py local")
            print("  python3 deploy_admin_roles.py deploy <user> <host> <path>")

    else:
        print("\n📝 ИНСТРУКЦИИ ДЛЯ РАЗВЕРТЫВАНИЯ:")
        print("\n1️⃣ РУЧНАЯ ОТПРАВКА:")
        print("   scp admin_roles.json user@server:/path/to/atra/")
        print("   scp apply_admin_roles_server.py user@server:/path/to/atra/")
        print("   scp deploy_admin_roles.sh user@server:/path/to/atra/")
        print("   ssh user@server 'cd /path/to/atra && ./deploy_admin_roles.sh'")

        print("\n2️⃣ АВТОМАТИЧЕСКАЯ ОТПРАВКА:")
        print("   python3 deploy_admin_roles.py deploy <user> <host> <path>")
        print("   Пример: python3 deploy_admin_roles.py deploy root 192.168.1.100 /opt/atra")

        print("\n3️⃣ НА СЕРВЕРЕ:")
        print("   python3 deploy_admin_roles.py local")
        print("   # или")
        print("   ./deploy_admin_roles.sh")

if __name__ == "__main__":
    main()
