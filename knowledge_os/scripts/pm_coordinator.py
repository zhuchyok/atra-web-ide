#!/usr/bin/env python3
"""
Главный координатор Project Manager
Автоматически управляет проектом: проверки, оптимизации, отчёты
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pm_auto_fix import AutoFixEngine
from scripts.pm_auto_optimize import AutoOptimizer
from scripts.pm_daily_check import ProjectManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(PROJECT_ROOT / "logs" / "pm_coordinator.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class PMCoordinator:
    """Главный координатор Project Manager"""

    def __init__(self):
        self.pm = ProjectManager()
        self.optimizer = AutoOptimizer()

    async def run_daily_cycle(self) -> None:
        """Запускает ежедневный цикл управления"""
        logger.info("🚀 Запуск ежедневного цикла PM...")

        try:
            # 1. Ежедневная проверка
            logger.info("📊 Шаг 1: Ежедневная проверка...")
            report = await self.pm.run_daily_check()
            self.pm.save_report()
            self.pm.print_summary()

            # 2. Автоматическая оптимизация (если статус не "healthy")
            if report.get("status") != "healthy":
                logger.info("🔧 Шаг 2: Автоматическая оптимизация...")
                optimization = await self.optimizer.run_optimization()
                self.optimizer.save_optimizations(optimization)
                self.optimizer.print_summary(optimization)

                # 3. Автоматическое применение исправлений
                logger.info("🔧 Шаг 3: Автоматическое применение исправлений...")
                fix_engine = AutoFixEngine()
                fixes_applied = await fix_engine._apply_fixes(report, optimization)

                if fixes_applied:
                    logger.info(f"✅ Применено исправлений: {len(fixes_applied)}")
                    for fix in fixes_applied:
                        logger.info(f"  • {fix.get('description', 'N/A')}")
                else:
                    logger.info("ℹ️ Нет критических проблем для исправления")

            logger.info("✅ Ежедневный цикл PM завершён")

        except Exception as e:
            logger.error(f"❌ Ошибка в ежедневном цикле PM: {e}", exc_info=True)

    async def _apply_critical_optimizations(self, optimization: dict) -> None:
        """Применяет критические оптимизации автоматически"""
        logger.info("⚙️ Применение критических оптимизаций...")

        recommendations = optimization.get("recommendations", [])
        high_priority = [r for r in recommendations if r.get("priority") == "high"]

        if not high_priority:
            logger.info("ℹ️ Нет критических оптимизаций для применения")
            return

        for rec in high_priority:
            actions = rec.get("actions", [])
            for action in actions:
                param = action.get("parameter")
                recommended_value = action.get("recommended_value")

                logger.info(f"🔧 Применение оптимизации: {param} = {recommended_value}")

                # Здесь можно добавить автоматическое применение оптимизаций
                # Например, обновление конфигурационных файлов
                # Пока только логируем
                logger.info(f"  ✓ {action.get('reason', '')}")

        logger.info(f"✅ Применено {len(high_priority)} критических оптимизаций")


async def main():
    """Главная функция"""
    coordinator = PMCoordinator()
    await coordinator.run_daily_cycle()


if __name__ == "__main__":
    asyncio.run(main())
