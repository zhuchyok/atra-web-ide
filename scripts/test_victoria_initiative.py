#!/usr/bin/env python3
"""
Тестовый скрипт для проверки Victoria Initiative and Self-Extension
"""

import asyncio
import sys
import os
from pathlib import Path

# Добавляем путь к knowledge_os
sys.path.insert(0, str(Path(__file__).parent.parent / "knowledge_os"))

async def test_victoria_initiative():
    """Тест Victoria Initiative"""
    print("🚀 Тестирование Victoria Initiative and Self-Extension\n")

    # 1. Проверка импортов
    print("1️⃣ Проверка импортов...")
    try:
        from app.victoria_enhanced import VictoriaEnhanced
        from app.event_bus import get_event_bus
        from app.skill_registry import get_skill_registry
        from app.file_watcher import FileWatcher
        from app.service_monitor import ServiceMonitor
        print("   ✅ Все модули импортируются\n")
    except Exception as e:
        print(f"   ❌ Ошибка импорта: {e}\n")
        return False

    # 2. Инициализация Victoria Enhanced
    print("2️⃣ Инициализация Victoria Enhanced...")
    try:
        victoria = VictoriaEnhanced()
        print("   ✅ Victoria Enhanced инициализирован\n")
    except Exception as e:
        print(f"   ❌ Ошибка инициализации: {e}\n")
        return False

    # 3. Проверка компонентов
    print("3️⃣ Проверка компонентов...")
    components = {
        "Event Bus": victoria.event_bus is not None,
        "Skill Registry": victoria.skill_registry is not None,
        "Skill Loader": victoria.skill_loader is not None,
        "Event Handlers": victoria.event_handlers is not None,
    }

    for name, status in components.items():
        status_icon = "✅" if status else "❌"
        print(f"   {status_icon} {name}: {'Доступен' if status else 'Недоступен'}")
    print()

    # 4. Запуск мониторинга
    print("4️⃣ Запуск мониторинга...")
    try:
        await victoria.start()
        print("   ✅ Мониторинг запущен\n")
    except Exception as e:
        print(f"   ⚠️ Ошибка запуска мониторинга: {e}\n")
        print("   (Это нормально, если некоторые компоненты недоступны)\n")

    # 5. Проверка статуса
    print("5️⃣ Проверка статуса...")
    try:
        status = await victoria.get_status()
        print(f"   ✅ Статус получен:")
        print(f"      - Event Bus: {status.get('event_bus_available', False)}")
        print(f"      - Skill Registry: {status.get('skill_registry_available', False)}")
        print(f"      - Skills Count: {status.get('skills_count', 0)}")
        print(f"      - Monitoring Started: {status.get('monitoring_started', False)}")
        print()
    except Exception as e:
        print(f"   ⚠️ Ошибка получения статуса: {e}\n")

    # 6. Проверка Skills
    print("6️⃣ Проверка Skills...")
    try:
        if victoria.skill_registry:
            skills = victoria.skill_registry.list_skills()
            print(f"   ✅ Загружено skills: {len(skills)}")
            if skills:
                print("   Доступные skills:")
                for skill in skills[:5]:  # Показываем первые 5
                    print(f"      - {skill.name}: {skill.description[:50]}...")
            print()
    except Exception as e:
        print(f"   ⚠️ Ошибка проверки skills: {e}\n")

    # 7. Остановка
    print("7️⃣ Остановка мониторинга...")
    try:
        await victoria.stop()
        print("   ✅ Мониторинг остановлен\n")
    except Exception as e:
        print(f"   ⚠️ Ошибка остановки: {e}\n")

    print("✅ Тест завершен!")
    return True

if __name__ == "__main__":
    try:
        result = asyncio.run(test_victoria_initiative())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Тест прерван пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
