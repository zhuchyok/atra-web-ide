#!/usr/bin/env python3
"""
🤖 АВТОМАТИЧЕСКОЕ ОБУЧЕНИЕ ИИ НА ИСТОРИЧЕСКИХ ДАННЫХ
Интеграция анализа исторических данных с системой обучения
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict

from src.shared.utils.datetime_utils import get_utc_now

# Импорты
try:
    from src.ai.historical_analysis import HistoricalDataAnalyzer
    from src.ai.integration import AIIntegration
    from src.ai.learning import AILearningSystem
    from src.ai.monitor import AIMonitor
    # from shared_utils import load_user_data_for_signals  # Не используется
except ImportError as e:
    logging.warning("Не удалось импортировать модули: %s", e)

logger = logging.getLogger(__name__)


class AutoLearningSystem:
    """Автоматическая система обучения ИИ"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AutoLearningSystem, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Предотвращаем повторную инициализацию
        if AutoLearningSystem._initialized:
            return
        AutoLearningSystem._initialized = True
        # Используем singleton registry для получения единственного экземпляра
        try:
            from src.ai.singleton import get_ai_learning_system

            self.ai_learning = get_ai_learning_system()
            logger.info("✅ Используем singleton экземпляр ИИ системы в автообучении")
        except (ImportError, AttributeError) as e:
            logger.warning(
                "⚠️ Singleton registry недоступен в автообучении, создаем новый экземпляр: %s", e
            )
            self.ai_learning = AILearningSystem()
        self.ai_integration = AIIntegration()
        self.ai_monitor = AIMonitor()
        self.historical_analyzer = HistoricalDataAnalyzer()

        # Настройки автоматического обучения
        self.learning_schedule = {
            "historical_analysis": 24 * 3600,  # Каждые 24 часа
            "pattern_analysis": 6 * 3600,  # Каждые 6 часов
            "optimization": 12 * 3600,  # Каждые 12 часов
            "report_generation": 24 * 3600,  # Каждые 24 часа
        }

        self.last_learning = {
            "historical_analysis": None,
            "pattern_analysis": None,
            "optimization": None,
            "report_generation": None,
        }

        logger.info("🤖 Автоматическая система обучения ИИ инициализирована")

    async def start_auto_learning(self):
        """Запускает автоматическое обучение"""
        logger.info("🚀 Запуск автоматического обучения ИИ...")

        while True:
            try:
                current_time = get_utc_now()

                # Проверяем расписание обучения
                await self._check_learning_schedule(current_time)

                # Пауза между проверками (1 час)
                await asyncio.sleep(3600)

            except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                logger.error("❌ Ошибка в автоматическом обучении: %s", e)
                await asyncio.sleep(300)  # 5 минут при ошибке

    async def _check_learning_schedule(self, current_time: datetime):
        """Проверяет расписание обучения"""
        try:
            for task_name, interval in self.learning_schedule.items():
                last_run = self.last_learning[task_name]

                if last_run is None or (current_time - last_run).total_seconds() >= interval:
                    logger.info("🔄 Выполняем задачу: %s", task_name)

                    if task_name == "historical_analysis":
                        await self._run_historical_analysis()
                    elif task_name == "pattern_analysis":
                        await self._run_pattern_analysis()
                    elif task_name == "optimization":
                        await self._run_optimization()
                    elif task_name == "report_generation":
                        await self._run_report_generation()

                    self.last_learning[task_name] = current_time

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка проверки расписания: %s", e)

    async def _run_historical_analysis(self):
        """Запускает анализ исторических данных"""
        try:
            logger.info("📊 Запуск анализа исторических данных...")

            # Выполняем полный анализ
            analysis = await self.historical_analyzer.analyze_all_historical_data()

            if analysis.get("patterns_learned", 0) > 0:
                logger.info(
                    "✅ Изучено %d новых паттернов из исторических данных",
                    analysis["patterns_learned"],
                )

                # Сохраняем результаты
                self.ai_learning.save_patterns()
                self.ai_learning.save_learning_model()
                self.ai_learning.save_metrics()
            else:
                logger.info("📊 Новых паттернов из исторических данных не найдено")

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа исторических данных: %s", e)

    async def _run_pattern_analysis(self):
        """Запускает анализ паттернов"""
        try:
            logger.info("🔍 Запуск анализа паттернов...")

            # Анализируем существующие паттерны
            analysis = self.ai_learning.analyze_patterns()

            if analysis.get("total_patterns", 0) > 0:
                logger.info("📊 Проанализировано %d паттернов", analysis["total_patterns"])

                # Получаем рекомендации
                recommendations = self.ai_learning.get_learning_recommendations()
                if recommendations:
                    logger.info("💡 Сгенерировано %d рекомендаций", len(recommendations))
                    for rec in recommendations:
                        logger.info("  • %s", rec)
            else:
                logger.info("📊 Паттернов для анализа не найдено")

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа паттернов: %s", e)

    async def _run_optimization(self):
        """Запускает оптимизацию параметров"""
        try:
            logger.info("🔧 Запуск оптимизации параметров...")

            # Выполняем автоматическую оптимизацию
            optimization = self.ai_learning.auto_optimize_parameters()

            if optimization.get("improvements"):
                logger.info("✅ Применено %d оптимизаций", len(optimization["improvements"]))
                for improvement in optimization["improvements"]:
                    logger.info("  • %s", improvement)
            else:
                logger.info("🔧 Оптимизации не требуются")

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка оптимизации: %s", e)

    async def _run_report_generation(self):
        """Запускает генерацию отчетов"""
        try:
            logger.info("📋 Генерация отчетов обучения...")

            # Генерируем отчет об обучении
            learning_report = self.ai_learning.generate_learning_report()

            # Генерируем отчет мониторинга
            monitoring_report = await self.ai_monitor.get_monitoring_report()

            # Генерируем отчет интеграции
            integration_report = await self.ai_integration.generate_learning_report()

            # Сохраняем отчеты в файлы
            await self._save_reports(learning_report, monitoring_report, integration_report)

            logger.info("✅ Отчеты сгенерированы и сохранены")

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка генерации отчетов: %s", e)

    async def _save_reports(
        self, learning_report: str, monitoring_report: str, integration_report: str
    ):
        """Сохраняет отчеты в файлы"""
        try:
            reports_dir = "ai_reports"
            os.makedirs(reports_dir, exist_ok=True)

            timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")

            # Сохраняем отчет об обучении
            with open(f"{reports_dir}/learning_report_{timestamp}.txt", "w", encoding="utf-8") as f:
                f.write(learning_report)

            # Сохраняем отчет мониторинга
            with open(
                f"{reports_dir}/monitoring_report_{timestamp}.txt", "w", encoding="utf-8"
            ) as f:
                f.write(monitoring_report)

            # Сохраняем отчет интеграции
            with open(
                f"{reports_dir}/integration_report_{timestamp}.txt", "w", encoding="utf-8"
            ) as f:
                f.write(integration_report)

            logger.info("📁 Отчеты сохранены в папку %s", reports_dir)

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка сохранения отчетов: %s", e)

    async def force_historical_analysis(self):
        """Принудительно запускает анализ исторических данных"""
        logger.info("🔄 Принудительный запуск анализа исторических данных...")
        await self._run_historical_analysis()

    async def force_pattern_analysis(self):
        """Принудительно запускает анализ паттернов"""
        logger.info("🔄 Принудительный запуск анализа паттернов...")
        await self._run_pattern_analysis()

    async def force_optimization(self):
        """Принудительно запускает оптимизацию"""
        logger.info("🔄 Принудительный запуск оптимизации...")
        await self._run_optimization()

    async def get_learning_status(self) -> Dict[str, Any]:
        """Получает статус обучения"""
        try:
            status = {
                "timestamp": get_utc_now().isoformat(),
                "learning_active": True,
                "last_learning": self.last_learning,
                "schedule": self.learning_schedule,
                "ai_patterns": len(self.ai_learning.patterns),
                "ai_accuracy": self.ai_learning.metrics.accuracy,
                "ai_profit_factor": self.ai_learning.metrics.profit_factor,
            }

            return status

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка получения статуса обучения: %s", e)
            return {"error": str(e)}

    async def generate_comprehensive_report(self) -> str:
        """Генерирует комплексный отчет"""
        try:
            report = f"""
🤖 КОМПЛЕКСНЫЙ ОТЧЕТ АВТОМАТИЧЕСКОГО ОБУЧЕНИЯ ИИ
{"=" * 70}

⏰ ВРЕМЯ ГЕНЕРАЦИИ: {get_utc_now().strftime("%Y-%m-%d %H:%M:%S")}

📊 СТАТУС ОБУЧЕНИЯ:
• Система активна: 🟢 Да
• Всего паттернов: {len(self.ai_learning.patterns)}
• Точность: {self.ai_learning.metrics.accuracy:.1%}
• Profit Factor: {self.ai_learning.metrics.profit_factor:.2f}

🕐 РАСПИСАНИЕ ОБУЧЕНИЯ:
"""

            for task_name, interval in self.learning_schedule.items():
                last_run = self.last_learning[task_name]
                if last_run:
                    next_run = last_run + timedelta(seconds=interval)
                    report += f"• {task_name}: последний запуск {last_run.strftime('%H:%M:%S')}, следующий {next_run.strftime('%H:%M:%S')}\n"
                else:
                    report += f"• {task_name}: еще не запускался\n"

            # Добавляем отчеты компонентов
            report += "\n" + "=" * 70 + "\n"
            report += await self.ai_integration.generate_learning_report()

            return report

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка генерации комплексного отчета: %s", e)
            return f"❌ Ошибка генерации отчета: {e}"


# Глобальный экземпляр автоматического обучения
auto_learning = AutoLearningSystem()


async def start_auto_learning():
    """Запускает автоматическое обучение"""
    logger.info("🚀 Запуск автоматического обучения ИИ...")
    await auto_learning.start_auto_learning()


async def force_historical_analysis():
    """Принудительно запускает анализ исторических данных"""
    await auto_learning.force_historical_analysis()


async def get_learning_status():
    """Получает статус обучения"""
    return await auto_learning.get_learning_status()


async def generate_comprehensive_report():
    """Генерирует комплексный отчет"""
    return await auto_learning.generate_comprehensive_report()


if __name__ == "__main__":
    # Тестирование автоматического обучения
    print("🤖 Тестирование автоматического обучения ИИ...")

    async def test():
        # Принудительно запускаем анализ исторических данных
        await force_historical_analysis()

        # Получаем статус
        status = await get_learning_status()
        print(f"📊 Статус: {status}")

        # Генерируем отчет
        report = await generate_comprehensive_report()
        print(report)

    asyncio.run(test())
