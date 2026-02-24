#!/usr/bin/env python3
"""
Отправка всех задач Victoria
Запускать: python3 scripts/tell_victoria_all_tasks.py
"""

import requests
import json
import os

VICTORIA_URL = os.getenv("VICTORIA_URL", "http://192.168.1.64:8010")

def send_to_victoria():
    """Отправляет задачу Victoria"""
    print("=" * 60)
    print("📤 ОТПРАВКА ВСЕХ ЗАДАЧ VICTORIA")
    print("=" * 60)
    print()

    # Проверка доступности
    try:
        response = requests.get(f"{VICTORIA_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Victoria недоступна: {response.status_code}")
            return False
        print("✅ Victoria доступна")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False

    # Формируем задачу
    goal = """Прочитай файл ALL_TASKS_FOR_VICTORIA.md в корне проекта atra-web-ide.

Выполни ВСЕ 10 задач из списка последовательно:

1. Запусти все контейнеры Knowledge OS (Elasticsearch, Kibana, Prometheus, Grafana)
2. Проверь доступность всех сервисов через health endpoints
3. Проверь доступность с MacBook по IP 192.168.1.64
4. Настрой автозапуск через launchd service
5. Обнови PLAN.md с финальным статусом миграции
6. Обнови IP адреса 192.168.1.43 на 192.168.1.64 где нужно
7. Создай финальный отчет MIGRATION_COMPLETE_FINAL.md
8. Проверь все созданные скрипты на работоспособность
9. Проверь volumes и данные
10. Протестируй полный цикл (остановка → запуск → проверка)

Используй:
- Extended Thinking для планирования
- Swarm Intelligence для координации с экспертами
- Hierarchical Orchestration для управления выполнением

Параметры:
- Mac Studio: 192.168.1.64
- Пользователь: bikos
- Путь: ~/Documents/atra-web-ide
- Docker PATH: /usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH

После выполнения каждой задачи проверяй результат."""

    # Отправляем задачу
    try:
        print("\n📤 Отправка задачи Victoria...")
        print("   (это может занять 10-15 минут...)\n")

        response = requests.post(
            f"{VICTORIA_URL}/run",
            json={"goal": goal, "max_steps": 60},
            timeout=900,  # 15 минут
            stream=False
        )

        if response.status_code == 200:
            result = response.json()
            print("✅ Задача принята Victoria!")
            print(f"\n📋 Статус: {result.get('status', 'unknown')}")
            if result.get('output'):
                output = result.get('output', '')
                if isinstance(output, str):
                    print(f"\n📝 Результат (первые 500 символов):")
                    print(output[:500])
                else:
                    print(f"\n📝 Результат: {str(output)[:500]}")
            return True
        else:
            print(f"❌ Ошибка: {response.status_code}")
            print(f"Ответ: {response.text[:200]}")
            return False

    except requests.exceptions.Timeout:
        print("⏱️  Таймаут: Victoria не ответила за 15 минут")
        print("💡 Задача может выполняться, проверь логи:")
        print(f"   ssh bikos@192.168.1.64 'docker logs victoria-agent --tail 100 -f'")
        return True  # Задача может выполняться
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False

def main():
    success = send_to_victoria()

    print()
    print("=" * 60)
    if success:
        print("✅ ЗАДАЧА ОТПРАВЛЕНА VICTORIA")
        print()
        print("💡 Проверь выполнение:")
        print(f"   ssh bikos@192.168.1.64 'docker logs victoria-agent --tail 100 -f'")
    else:
        print("⚠️  НЕ УДАЛОСЬ ОТПРАВИТЬ ЧЕРЕЗ API")
        print()
        print("💡 Передай Victoria в Cursor на Mac Studio:")
        print("   @victoria Прочитай файл ALL_TASKS_FOR_VICTORIA.md")
        print("   в корне проекта. Выполни ВСЕ 10 задач из списка.")
    print("=" * 60)

if __name__ == "__main__":
    main()
