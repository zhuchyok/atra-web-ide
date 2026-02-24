#!/usr/bin/env python3
"""
Скрипт для инициализации Екатерины (Financial Analyst) в системе.

Создает:
- Базу знаний
- Программу обучения
- Интегрирует в систему постоянного обучения
"""

import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from observability.team_member_manager import get_team_member_manager


def main():
    """Инициализирует Екатерину в системе"""
    print("🚀 Инициализация Екатерины (Financial Analyst)...")

    # Получаем менеджер сотрудников
    manager = get_team_member_manager()

    # Проверяем, есть ли уже Екатерина
    ekaterina = manager.get_member("Екатерина")

    if ekaterina:
        print("✅ Екатерина уже в системе:")
        print(f"   - База знаний: {ekaterina.knowledge_base_path}")
        print(f"   - Программа обучения: {ekaterina.learning_program_path}")

        # Проверяем существование файлов
        if ekaterina.knowledge_base_path.exists():
            print("   ✅ База знаний существует")
        else:
            print("   ⚠️ База знаний не найдена, создаем...")
            manager._create_knowledge_base(ekaterina)

        if ekaterina.learning_program_path and ekaterina.learning_program_path.exists():
            print("   ✅ Программа обучения существует")
        else:
            print("   ⚠️ Программа обучения не найдена, создаем...")
            manager._create_learning_program(ekaterina)
    else:
        print("➕ Добавляем Екатерину в систему...")
        ekaterina = manager.add_new_member(
            name="Екатерина",
            role="Financial Analyst",
            priority=14,
            expertise=["финансы", "валидация", "аудит", "Decimal", "расчёты"],
        )

    print("\n✅ Екатерина успешно инициализирована!")
    print(f"   - База знаний: {ekaterina.knowledge_base_path}")
    print(f"   - Программа обучения: {ekaterina.learning_program_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
