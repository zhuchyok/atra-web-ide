#!/usr/bin/env python3
"""
🔍 АВТОМАТИЧЕСКИЙ МОНИТОРИНГ И ОБУЧЕНИЕ ИИ
Непрерывное наблюдение за системой и автоматическое обучение
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from src.shared.utils.datetime_utils import get_utc_now

# Импорты
try:
    from src.ai.integration import AIIntegration
    from src.ai.learning import AILearningSystem
    from src.utils.user_utils import load_user_data_for_signals
except ImportError as e:
    logging.warning("Не удалось импортировать модули: %s", e)

logger = logging.getLogger(__name__)


class AIMonitor:
    """Автоматический мониторинг и обучение ИИ"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AIMonitor, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Предотвращаем повторную инициализацию
        if AIMonitor._initialized:
            return
        AIMonitor._initialized = True
        # Используем singleton registry для получения единственного экземпляра
        try:
            from src.ai.singleton import get_ai_learning_system

            self.ai_learning = get_ai_learning_system()
            logger.info("✅ Используем singleton экземпляр ИИ системы в мониторе")
        except (ImportError, AttributeError) as e:
            logger.warning(
                "⚠️ Singleton registry недоступен в мониторе, создаем новый экземпляр: %s", e
            )
            self.ai_learning = AILearningSystem()
        self.ai_integration = AIIntegration()
        self.monitoring_active = True
        self.check_interval = 300  # 5 минут
        self.learning_interval = 3600  # 1 час

        # Статистика мониторинга
        self.stats = {
            "start_time": get_utc_now(),
            "checks_performed": 0,
            "errors_found": 0,
            "optimizations_applied": 0,
            "patterns_learned": 0,
        }

        logger.info("🔍 ИИ мониторинг инициализирован")

    async def start_monitoring(self):
        """Запускает непрерывный мониторинг"""
        logger.info("🚀 Запуск автоматического мониторинга ИИ...")

        while self.monitoring_active:
            try:
                # Выполняем проверки
                await self._perform_system_checks()

                # Обучение каждые N минут
                if (
                    self.stats["checks_performed"] % (self.learning_interval // self.check_interval)
                    == 0
                ):
                    await self._perform_learning_cycle()

                # Пауза между проверками
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                # Нормальная отмена задачи при shutdown
                logger.info("🛑 Мониторинг остановлен (задача отменена)")
                raise  # Пробрасываем дальше для корректного завершения
            except (RuntimeError, OSError) as e:
                logger.error("❌ Ошибка в мониторинге: %s", e)
                self.stats["errors_found"] += 1
                await asyncio.sleep(60)  # 1 минута при ошибке

    async def _perform_system_checks(self):
        """Выполняет проверки системы"""
        self.stats["checks_performed"] += 1

        logger.info("🔍 Проверка #%s...", self.stats["checks_performed"])

        # Проверка 1: Валидация данных
        validation = self.ai_learning.validate_system_data()
        if validation["errors"]:
            logger.warning("⚠️ Найдены ошибки: %s", validation["errors"])
            self.stats["errors_found"] += len(validation["errors"])

        # Проверка 2: Анализ производительности
        performance = await self._analyze_system_performance()
        if performance["issues"]:
            logger.warning("⚠️ Проблемы производительности: %s", performance["issues"])

        # Проверка 3: Мониторинг API
        api_status = await self._check_api_status()
        if api_status["problems"]:
            logger.warning("⚠️ Проблемы API: %s", api_status["problems"])

        logger.info("✅ Проверка #%s завершена", self.stats["checks_performed"])

    async def _analyze_system_performance(self) -> Dict[str, Any]:
        """Анализирует производительность системы"""
        try:
            performance = {
                "timestamp": get_utc_now().isoformat(),
                "issues": [],
                "recommendations": [],
                "data_status": {},
            }

            # Проверка размера файлов данных
            try:
                from src.config.patterns import get_patterns_file_path
            except ImportError:
                from patterns_config import get_patterns_file_path

            data_files = ["user_data.json", get_patterns_file_path("main")]

            for file in data_files:
                if os.path.exists(file):
                    size_mb = os.path.getsize(file) / (1024 * 1024)
                    if size_mb > 100:  # Больше 100MB
                        performance["issues"].append(f"📁 Большой файл {file}: {size_mb:.1f}MB")
                        performance["recommendations"].append(
                            f"💡 Рекомендуется архивировать {file}"
                        )

            # Проверка базы данных вместо signal_history.json
            try:
                import sqlite3

                conn = sqlite3.connect("trading.db")
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM signals_log")
                signal_count = cursor.fetchone()[0]
                conn.close()

                if signal_count > 0:
                    performance["data_status"]["signals_in_db"] = signal_count
                    performance["recommendations"].append(
                        f"✅ История сигналов в БД: {signal_count:,} записей"
                    )
                else:
                    # Проверяем, сколько времени работает система
                    system_uptime_hours = (
                        get_utc_now() - self.stats["start_time"]
                    ).total_seconds() / 3600

                    # Показываем предупреждение только если система работает больше 2 часов без сигналов
                    if system_uptime_hours > 2:
                        performance["issues"].append("❌ База данных сигналов пуста")
                    else:
                        performance["recommendations"].append(
                            "ℹ️ База данных сигналов пуста (система недавно запущена)"
                        )
            except (sqlite3.Error, OSError) as e:
                performance["issues"].append(f"❌ Ошибка проверки БД: {e}")

            # Проверка количества паттернов
            pattern_count = len(self.ai_learning.patterns)
            if pattern_count > 30000:
                performance["issues"].append(f"📊 Много паттернов: {pattern_count}")
                performance["recommendations"].append("💡 Система автоматически очистит паттерны")
            elif pattern_count > 25000:
                performance["recommendations"].append(
                    f"ℹ️ Паттернов: {pattern_count}/30000 - автоочистка скоро"
                )

            return performance

        except (OSError, RuntimeError) as e:
            logger.error("❌ Ошибка анализа производительности: %s", e)
            return {"issues": [f"Ошибка анализа: {e}"], "recommendations": []}

    async def _check_api_status(self) -> Dict[str, Any]:
        """Проверяет статус API"""
        try:
            api_status = {
                "timestamp": get_utc_now().isoformat(),
                "problems": [],
                "recommendations": [],
            }

            # Проверка доступности основных API
            apis_to_check = [
                ("Binance", "https://api.binance.com/api/v3/ping"),
                ("Bybit", "https://api.bybit.com/v5/market/time"),
                ("CoinGecko", "https://api.coingecko.com/api/v3/ping"),
            ]

            for name, url in apis_to_check:
                try:
                    import aiohttp

                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=10) as response:
                            if response.status != 200:
                                # Для CoinGecko 429 ошибка не критична (rate limiting)
                                if name == "CoinGecko" and response.status == 429:
                                    api_status["problems"].append(
                                        f"⚠️ {name} API rate limited (статус: {response.status}) - ожидание"
                                    )
                                else:
                                    api_status["problems"].append(
                                        f"❌ {name} API недоступен (статус: {response.status})"
                                    )
                except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
                    api_status["problems"].append(f"❌ {name} API ошибка: {e}")

            return api_status

        except (aiohttp.ClientError, RuntimeError) as e:
            logger.error("❌ Ошибка проверки API: %s", e)
            return {"problems": [f"Ошибка проверки API: {e}"], "recommendations": []}

    async def _perform_learning_cycle(self):
        """Выполняет цикл обучения"""
        logger.info("🧠 Выполнение цикла обучения...")

        try:
            # Анализ новых паттернов
            new_patterns = await self._analyze_new_patterns()
            if new_patterns:
                self.stats["patterns_learned"] += len(new_patterns)
                logger.info("📊 Изучено %s новых паттернов", len(new_patterns))

            # Оптимизация параметров
            optimization = self.ai_learning.auto_optimize_parameters()
            if optimization["improvements"]:
                self.stats["optimizations_applied"] += len(optimization["improvements"])
                logger.info("🔧 Применено %s оптимизаций", len(optimization["improvements"]))

            # Генерация отчета
            # report = await self.ai_integration.generate_learning_report()
            logger.info("📊 Отчет об обучении сгенерирован")

        except (RuntimeError, OSError) as e:
            logger.error("❌ Ошибка в цикле обучения: %s", e)

    async def _analyze_new_patterns(self) -> List[Dict[str, Any]]:
        """Анализирует новые паттерны"""
        try:
            new_patterns = []

            # Получаем данные пользователей
            user_data = load_user_data_for_signals()
            if not user_data:
                return new_patterns

            # Анализируем каждый символ
            symbols_to_analyze = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT"]

            for symbol in symbols_to_analyze:
                try:
                    # Получаем рекомендации ИИ
                    recommendations = await self.ai_integration.get_ai_recommendations(symbol)

                    if recommendations.get("confidence", 0) > 0.7:
                        new_patterns.append(
                            {
                                "symbol": symbol,
                                "confidence": recommendations["confidence"],
                                "recommendations": recommendations["recommendations"],
                            }
                        )

                except (RuntimeError, OSError) as e:
                    logger.error("❌ Ошибка анализа %s: %s", symbol, e)

            return new_patterns

        except (RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа новых паттернов: %s", e)
            return []

    async def get_monitoring_report(self) -> str:
        """Генерирует отчет мониторинга"""
        try:
            uptime = get_utc_now() - self.stats["start_time"]

            report = f"""
🔍 ОТЧЕТ АВТОМАТИЧЕСКОГО МОНИТОРИНГА ИИ
{"=" * 60}

⏰ ВРЕМЯ РАБОТЫ:
• Запущен: {self.stats["start_time"].strftime("%Y-%m-%d %H:%M:%S")}
• Время работы: {uptime}
• Проверок выполнено: {self.stats["checks_performed"]}
• Ошибок найдено: {self.stats["errors_found"]}

🧠 ОБУЧЕНИЕ:
• Паттернов изучено: {self.stats["patterns_learned"]}
• Оптимизаций применено: {self.stats["optimizations_applied"]}
• Статус: {"🟢 Активно" if self.monitoring_active else "🔴 Отключено"}

📊 СТАТИСТИКА СИСТЕМЫ:
• Всего паттернов: {len(self.ai_learning.patterns)}
• Точность: {self.ai_learning.metrics.accuracy:.1%}
• Profit Factor: {self.ai_learning.metrics.profit_factor:.2f}

💡 РЕКОМЕНДАЦИИ:
"""

            # Получаем рекомендации
            recommendations = self.ai_learning.get_learning_recommendations()
            for rec in recommendations:
                report += f"• {rec}\n"

            return report

        except (RuntimeError, OSError) as e:
            logger.error("❌ Ошибка генерации отчета мониторинга: %s", e)
            return f"❌ Ошибка генерации отчета: {e}"

    async def stop_monitoring(self):
        """Останавливает мониторинг"""
        self.monitoring_active = False
        logger.info("🛑 Мониторинг остановлен")

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику мониторинга"""
        return {
            **self.stats,
            "monitoring_active": self.monitoring_active,
            "ai_patterns": len(self.ai_learning.patterns),
            "ai_accuracy": self.ai_learning.metrics.accuracy,
        }


# Глобальный экземпляр мониторинга
ai_monitor = AIMonitor()


async def start_ai_monitoring():
    """Запускает автоматический мониторинг ИИ"""
    logger.info("🚀 Запуск автоматического мониторинга ИИ...")
    await ai_monitor.start_monitoring()


async def get_ai_status():
    """Получает статус ИИ системы"""
    try:
        report = await ai_monitor.get_monitoring_report()
        return report
    except (RuntimeError, OSError) as e:
        return f"❌ Ошибка получения статуса: {e}"


if __name__ == "__main__":
    # Тестирование мониторинга
    print("🔍 Тестирование автоматического мониторинга ИИ...")

    async def test():
        # Генерируем отчет
        report = await get_ai_status()
        print(report)

        # Получаем статистику
        stats = ai_monitor.get_stats()
        print(f"\n📊 Статистика: {stats}")

    asyncio.run(test())
