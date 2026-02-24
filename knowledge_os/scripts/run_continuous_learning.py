#!/usr/bin/env python3
"""
Скрипт для запуска постоянного обучения всех сотрудников.

Автоматически:
- Инициализирует всех сотрудников (включая новых)
- Обновляет базы знаний
- Обновляет программы обучения
- Собирает метрики обучения
"""

import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from observability.continuous_learning import get_continuous_learning_system
from observability.team_member_manager import get_team_member_manager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Запускает цикл постоянного обучения"""
    logger.info("🚀 Запуск системы постоянного обучения...")

    # Получаем систему обучения
    learning_system = get_continuous_learning_system()

    # Запускаем цикл обучения
    result = learning_system.run_continuous_learning_cycle()

    # Выводим результаты
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ ОБУЧЕНИЯ")
    print("=" * 60)
    print(f"✅ Обновлено сотрудников: {result['members_updated']}")
    print(f"✅ Обновлено программ: {result['programs_updated']}")
    print(f"✅ База знаний обновлена: {result['knowledge_base_updated']}")
    print("\n📈 МЕТРИКИ ОБУЧЕНИЯ:")
    metrics = result["learning_metrics"]
    print(f"   - Всего сотрудников: {metrics['total_members']}")
    print(f"   - Активных: {metrics['active_members']}")
    print(f"   - С базой знаний: {metrics['members_with_knowledge_base']}")
    print(f"   - Покрытие: {metrics['coverage_percentage']:.1f}%")

    print("\n👥 ОБНОВЛЕННЫЕ СОТРУДНИКИ:")
    for member_info in result["members"]:
        status = "✅" if member_info.get("updated") else "⚠️"
        print(f"   {status} {member_info['member']} ({member_info['role']})")
        if "error" in member_info:
            print(f"      Ошибка: {member_info['error']}")

    print("\n" + "=" * 60)
    logger.info("✅ Обучение завершено успешно!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
