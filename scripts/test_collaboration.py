#!/usr/bin/env python3
"""
Тест Multi-Agent Collaboration
Проверка координации между Victoria и Veronica
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../knowledge_os'))

from app.multi_agent_collaboration import MultiAgentCollaboration, TaskType
from app.task_delegation import TaskDelegator

async def test_simple_delegation():
    """Тест простого делегирования"""
    print("=" * 60)
    print("🧪 Тест 1: Простое делегирование")
    print("=" * 60)
    
    collaboration = MultiAgentCollaboration()
    delegator = TaskDelegator()
    
    # Задача для Victoria (планирование)
    print("\n📋 Задача 1: Планирование")
    task1 = await delegator.delegate_smart("Спланируй разработку веб-приложения")
    print(f"  Делегировано: {task1.assigned_to}")
    print(f"  Тип: {task1.task_type.value}")
    
    # Задача для Veronica (выполнение)
    print("\n📋 Задача 2: Выполнение")
    task2 = await delegator.delegate_smart("Прочитай файл src/main.py")
    print(f"  Делегировано: {task2.assigned_to}")
    print(f"  Тип: {task2.task_type.value}")
    
    # Задача для Veronica (файлы)
    print("\n📋 Задача 3: Файловая операция")
    task3 = await delegator.delegate_smart("Создай файл test.txt с содержимым 'Hello'")
    print(f"  Делегировано: {task3.assigned_to}")
    print(f"  Тип: {task3.task_type.value}")

async def test_complex_coordination():
    """Тест координации сложной задачи"""
    print("\n" + "=" * 60)
    print("🧪 Тест 2: Координация сложной задачи")
    print("=" * 60)
    
    collaboration = MultiAgentCollaboration()
    
    print("\n📋 Сложная задача: Разработка и тестирование API")
    result = await collaboration.coordinate_complex_task(
        "Разработай REST API для управления пользователями и напиши тесты"
    )
    
    print(f"\n✅ Успех: {result.success}")
    print(f"📊 Участники: {', '.join(result.participants)}")
    print(f"⏱️  Длительность: {result.total_duration:.2f}s")
    print(f"\n📝 Шаги координации:")
    for i, step in enumerate(result.coordination_steps, 1):
        print(f"  {i}. {step}")
    
    if result.result:
        print(f"\n📄 Результат: {str(result.result)[:200]}...")

async def test_conflict_resolution():
    """Тест разрешения конфликтов"""
    print("\n" + "=" * 60)
    print("🧪 Тест 3: Разрешение конфликтов")
    print("=" * 60)
    
    collaboration = MultiAgentCollaboration()
    
    print("\n⚔️ Конфликт: Выбор технологии для проекта")
    agent_opinions = {
        "Victoria": "Использовать Python + FastAPI для бэкенда",
        "Veronica": "Использовать Node.js + Express для бэкенда"
    }
    
    resolution = await collaboration.resolve_conflict(
        "Выбор технологии для нового веб-проекта",
        agent_opinions
    )
    
    print(f"\n✅ Решение: {resolution[:200]}...")

async def main():
    """Главная функция"""
    print("🚀 MULTI-AGENT COLLABORATION TESTS")
    print("=" * 60)
    
    try:
        await test_simple_delegation()
        # await test_complex_coordination()  # Раскомментировать когда агенты доступны
        # await test_conflict_resolution()  # Раскомментировать когда агенты доступны
        
        print("\n" + "=" * 60)
        print("✅ Тесты завершены!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
