#!/usr/bin/env python3
"""
Отправка контекста чата в Veronica на Mac Studio
Запускать: python3 scripts/send_chat_context_to_veronica.py
"""

import requests
import json
import os
from pathlib import Path

# URL Veronica на Mac Studio
VERONICA_URL = os.getenv("VERONICA_URL", "http://192.168.1.64:8011")

def get_chat_context():
    """Собирает контекст из всех файлов миграции и отчетов"""
    context_parts = []
    
    # Файлы с контекстом миграции
    context_files = [
        "FINAL_MIGRATION_REPORT.md",
        "MIGRATION_STATUS.md",
        "MIGRATION_COMPLETE.md",
        "COMPLETE_MIGRATION_REPORT.md",
        "FINAL_DOCKER_CHECK.md",
        "MIGRATION_FINAL_STATUS.md",
        "CHECK_CONTAINERS_ON_MAC_STUDIO.md",
        "MIGRATION_INSTRUCTIONS.md",
    ]
    
    root = Path(__file__).parent.parent
    
    for filename in context_files:
        filepath = root / filename
        if filepath.exists():
            try:
                content = filepath.read_text(encoding='utf-8')
                context_parts.append(f"=== {filename} ===\n{content}\n")
            except Exception as e:
                print(f"⚠️  Ошибка чтения {filename}: {e}")
    
    # Добавляем информацию о скриптах миграции
    scripts_info = """
=== СКРИПТЫ МИГРАЦИИ ===

Созданные скрипты для миграции Docker контейнеров с MacBook на Mac Studio:

1. scripts/full_migration_macbook_to_macstudio.sh
   - Полная миграция одной командой

2. scripts/migrate_docker_to_mac_studio.sh
   - Экспорт всех volumes и образов

3. scripts/import_docker_from_macbook.sh
   - Импорт на Mac Studio

4. scripts/migrate_root_containers.sh
   - Миграция корневых контейнеров (frontend, backend)

5. scripts/import_root_containers.sh
   - Импорт корневых контейнеров

6. scripts/check_and_start_containers.sh
   - Проверка и запуск контейнеров

7. scripts/start_all_on_mac_studio.sh
   - Полный запуск всех сервисов

8. START_ON_MAC_STUDIO.sh
   - Простой скрипт запуска

=== КЛЮЧЕВЫЕ МОМЕНТЫ МИГРАЦИИ ===

1. Mac Studio IP: 192.168.1.64
2. Пользователь Mac Studio: bikos
3. Все контейнеры перенесены с MacBook на Mac Studio
4. Knowledge OS контейнеры работают (Victoria, Veronica, API, Database)
5. Корневые контейнеры импортированы (Frontend, Backend)
6. Docker Desktop установлен и запущен на Mac Studio
7. Все volumes и образы экспортированы и импортированы

=== СТРУКТУРА ПРОЕКТА ===

- knowledge_os/docker-compose.yml - основные сервисы (Victoria, Veronica, Knowledge OS)
- docker-compose.yml - корневые контейнеры (Frontend, Backend, Web IDE)
- scripts/ - все скрипты миграции и управления
- docs/mac-studio/ - документация по Mac Studio

"""
    context_parts.append(scripts_info)
    
    return "\n".join(context_parts)

def send_to_veronica(context: str):
    """Отправляет контекст в Veronica"""
    print(f"🔗 Подключение к Veronica: {VERONICA_URL}")
    
    # Проверка доступности
    try:
        response = requests.get(f"{VERONICA_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Veronica недоступна: {response.status_code}")
            return False
        print("✅ Veronica доступна")
    except Exception as e:
        print(f"❌ Ошибка подключения к Veronica: {e}")
        return False
    
    # Формируем задачу для Veronica
    task = f"""Изучи весь контекст миграции Docker контейнеров с MacBook на Mac Studio.

КОНТЕКСТ:
{context}

ЗАДАЧА:
1. Изучи все документы и скрипты миграции
2. Пойми структуру проекта и архитектуру
3. Запомни ключевые моменты:
   - IP Mac Studio: 192.168.1.64
   - Пользователь: bikos
   - Все контейнеры перенесены
   - Knowledge OS работает
   - Корневые контейнеры импортированы
4. Будь готова отвечать на вопросы о миграции, контейнерах, структуре проекта

Используй Extended Thinking для глубокого анализа контекста."""
    
    # Отправляем через API Veronica
    try:
        print("\n📤 Отправка контекста в Veronica...")
        print("   (это может занять некоторое время...)\n")
        
        # Используем /run endpoint если есть, иначе /chat
        endpoints = ["/run", "/chat", "/message"]
        result = None
        
        for endpoint in endpoints:
            try:
                if endpoint == "/run":
                    response = requests.post(
                        f"{VERONICA_URL}{endpoint}",
                        json={"goal": task, "max_steps": 20},
                        timeout=300,
                        stream=False
                    )
                else:
                    response = requests.post(
                        f"{VERONICA_URL}{endpoint}",
                        json={"message": task, "context": context},
                        timeout=300,
                        stream=False
                    )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Успешно отправлено через {endpoint}")
                    break
            except requests.exceptions.RequestException:
                continue
        
        if result:
            print("\n📋 Ответ Veronica:")
            if isinstance(result, dict):
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(result)
            return True
        else:
            print("❌ Не удалось отправить через доступные endpoints")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False

def main():
    print("=" * 60)
    print("📚 ОТПРАВКА КОНТЕКСТА ЧАТА В VERONICA")
    print("=" * 60)
    print()
    
    # Собираем контекст
    print("📖 Сбор контекста...")
    context = get_chat_context()
    print(f"   ✅ Собрано {len(context)} символов контекста")
    print()
    
    # Отправляем в Veronica
    success = send_to_veronica(context)
    
    print()
    print("=" * 60)
    if success:
        print("✅ КОНТЕКСТ УСПЕШНО ОТПРАВЛЕН В VERONICA")
    else:
        print("⚠️  НЕ УДАЛОСЬ ОТПРАВИТЬ КОНТЕКСТ")
        print()
        print("💡 Альтернативный способ:")
        print("   1. Сохрани контекст в файл")
        print("   2. Отправь через curl:")
        print(f"      curl -X POST {VERONICA_URL}/run \\")
        print("        -H 'Content-Type: application/json' \\")
        print("        -d '{\"goal\": \"Изучи контекст из файла...\", \"max_steps\": 20}'")
    print("=" * 60)

if __name__ == "__main__":
    main()
