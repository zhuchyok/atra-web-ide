"""
Периодический запуск автоматических ретроспектив и обновления базы знаний.

Запускается каждые 24 часа для:
1. Сбора ретроспектив за прошедший период
2. Обновления базы знаний
3. Интеграции lessons learned
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from observability.continuous_learning import get_continuous_learning_system
from observability.feedback import FeedbackAggregator
from observability.knowledge_applicator import apply_all_knowledge
from observability.knowledge_base import update_knowledge_base

logger = logging.getLogger(__name__)


async def run_retrospective_scheduler():
    """
    Периодически запускает обновление базы знаний и сбор lessons learned.

    Запускается каждые 24 часа.
    """
    logger.info("🔄 Запуск планировщика ретроспектив и обновления базы знаний")

    while True:
        try:
            # Ждем 24 часа
            await asyncio.sleep(24 * 60 * 60)  # 24 часа

            logger.info("📚 Автоматическое применение всех изученных знаний...")

            # Применяем все знания (guidance, база знаний, эволюция промптов)
            try:
                results = apply_all_knowledge()
                logger.info("✅ Применение знаний завершено: %s", results)
            except Exception as e:
                logger.error("❌ Ошибка применения знаний: %s", e, exc_info=True)

            # Запускаем постоянное обучение для всех сотрудников
            logger.info("🔄 Запуск постоянного обучения всех сотрудников...")
            try:
                learning_system = get_continuous_learning_system()
                learning_result = learning_system.run_continuous_learning_cycle()
                logger.info(
                    "✅ Постоянное обучение завершено: обновлено %d сотрудников",
                    learning_result["members_updated"],
                )
            except Exception as e:
                logger.error("❌ Ошибка постоянного обучения: %s", e, exc_info=True)

            logger.info("✅ Автоматическое обновление завершено")

        except asyncio.CancelledError:
            logger.info("🛑 Планировщик ретроспектив остановлен")
            break
        except Exception as e:
            logger.error("❌ Критическая ошибка в планировщике ретроспектив: %s", e, exc_info=True)
            # Ждем 1 час перед повторной попыткой
            await asyncio.sleep(60 * 60)


async def run_retrospective_scheduler_task():
    """Обертка для запуска планировщика как задачи"""
    await run_retrospective_scheduler()
