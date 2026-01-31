#!/usr/bin/env python3
"""
Проверка интеграции Victoria Initiative во всех компонентах
"""

import os
import sys
from pathlib import Path

def check_file(file_path, patterns):
    """Проверить наличие паттернов в файле"""
    if not os.path.exists(file_path):
        return False, f"Файл не найден: {file_path}"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            found = []
            missing = []
            for pattern in patterns:
                if pattern in content:
                    found.append(pattern)
                else:
                    missing.append(pattern)
            return len(missing) == 0, {"found": found, "missing": missing}
    except Exception as e:
        return False, str(e)

def main():
    """Проверка всех интеграций"""
    print("🔍 Проверка интеграции Victoria Initiative\n")
    
    checks = []
    
    # 1. Victoria Server
    print("1️⃣ Проверка Victoria Server...")
    patterns = [
        "victoria_enhanced_instance",
        "ENABLE_EVENT_MONITORING",
        "lifespan",
        "await victoria_enhanced_instance.start()"
    ]
    ok, result = check_file("src/agents/bridge/victoria_server.py", patterns)
    if ok:
        print("   ✅ Все паттерны найдены")
    else:
        print(f"   ⚠️ Отсутствуют: {result.get('missing', [])}")
    checks.append(("Victoria Server", ok))
    print()
    
    # 2. Docker Compose
    print("2️⃣ Проверка Docker Compose...")
    patterns = [
        "ENABLE_EVENT_MONITORING",
        "FILE_WATCHER_ENABLED",
        "SERVICE_MONITOR_ENABLED"
    ]
    ok, result = check_file("knowledge_os/docker-compose.yml", patterns)
    if ok:
        print("   ✅ Все переменные найдены")
    else:
        print(f"   ⚠️ Отсутствуют: {result.get('missing', [])}")
    checks.append(("Docker Compose", ok))
    print()
    
    # 3. .env файл
    print("3️⃣ Проверка .env...")
    if os.path.exists(".env"):
        with open(".env", 'r') as f:
            env_content = f.read()
            if "ENABLE_EVENT_MONITORING" in env_content:
                print("   ✅ ENABLE_EVENT_MONITORING настроен")
                checks.append((".env", True))
            else:
                print("   ⚠️ ENABLE_EVENT_MONITORING не найден")
                checks.append((".env", False))
    else:
        print("   ⚠️ .env файл не найден")
        checks.append((".env", False))
    print()
    
    # 4. Файлы компонентов
    print("4️⃣ Проверка файлов компонентов...")
    files = [
        "knowledge_os/app/file_watcher.py",
        "knowledge_os/app/service_monitor.py",
        "knowledge_os/app/skill_registry.py",
        "knowledge_os/app/skill_loader.py",
        "knowledge_os/app/skill_discovery.py",
        "knowledge_os/app/skill_state_machine.py",
        "knowledge_os/app/victoria_event_handlers.py"
    ]
    all_exist = True
    for file_path in files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} - не найден")
            all_exist = False
    checks.append(("Компоненты", all_exist))
    print()
    
    # 5. Миграция БД
    print("5️⃣ Проверка миграции БД...")
    if os.path.exists("knowledge_os/db/migrations/add_skills_tables.sql"):
        print("   ✅ Миграция найдена")
        checks.append(("Миграция БД", True))
    else:
        print("   ❌ Миграция не найдена")
        checks.append(("Миграция БД", False))
    print()
    
    # Итог
    print("=" * 50)
    print("📊 Итоговый статус:")
    print()
    all_ok = True
    for name, status in checks:
        icon = "✅" if status else "❌"
        print(f"   {icon} {name}")
        if not status:
            all_ok = False
    
    print()
    if all_ok:
        print("✅ Все проверки пройдены! Интеграция завершена.")
    else:
        print("⚠️ Некоторые проверки не пройдены. Проверьте выше.")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
