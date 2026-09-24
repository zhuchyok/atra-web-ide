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
    logger.info("\n" + "=" * 60)
    logger.info("📊 РЕЗУЛЬТАТЫ ОБУЧЕНИЯ")
    logger.info("=" * 60)
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"✅ Обновлено сотрудников: {result['members_updated']}")
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"✅ Обновлено программ: {result['programs_updated']}")
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"✅ База знаний обновлена: {result['knowledge_base_updated']}")
    logger.info("\n📈 МЕТРИКИ ОБУЧЕНИЯ:")
    metrics = result["learning_metrics"]
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"   - Всего сотрудников: {metrics['total_members']}")
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"   - Активных: {metrics['active_members']}")
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"   - С базой знаний: {metrics['members_with_knowledge_base']}")
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"   - Покрытие: {metrics['coverage_percentage']:.1f}%")

    logger.info("\n👥 ОБНОВЛЕННЫЕ СОТРУДНИКИ:")
    for member_info in result["members"]:
        status = "✅" if member_info.get("updated") else "⚠️"
        # TODO: Convert f-string to %s formatting for performance
        logger.info(f"   {status} {member_info['member']} ({member_info['role']})")
        if "error" in member_info:
            # TODO: Convert f-string to %s formatting for performance
            logger.info(f"      Ошибка: {member_info['error']}")

    logger.info("\n" + "=" * 60)
    logger.info("✅ Обучение завершено успешно!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
