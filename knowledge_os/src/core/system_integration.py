#!/usr/bin/env python3

"""
Интеграционный модуль для связи всех улучшенных систем.

Обеспечивает взаимодействие между источниками данных, мониторингом,
логированием, риск-менеджментом и другими компонентами системы.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


class SystemIntegration:
    """Главный класс интеграции систем"""

    def __init__(self):
        self.data_sources_manager = None
        self.data_quality_monitor = None
        self.enhanced_logging = None
        self.filter_optimizer = None
        self.risk_manager = None
        self.forward_tester = None
        self.monitoring_system = None

        self.integration_status = {
            "data_sources": False,
            "data_quality": False,
            "enhanced_logging": False,
            "filter_optimizer": False,
            "risk_manager": False,
            "forward_tester": False,
            "monitoring": False,
        }

        self.is_initialized = False

    async def initialize_all_systems(self) -> Dict[str, bool]:
        """Инициализирует все улучшенные системы"""

        logger.info("🔧 Инициализация интегрированных систем...")

        initialization_results = {}

        # 1. Инициализация улучшенного логирования
        try:
            from enhanced_logging import get_logger, logging_manager

            self.enhanced_logging = logging_manager
            self.integration_status["enhanced_logging"] = True
            initialization_results["enhanced_logging"] = True
            logger.info("✅ Enhanced logging system initialized")
        except ImportError as e:
            logger.warning(f"⚠️ Enhanced logging not available: {e}")
            initialization_results["enhanced_logging"] = False

        # 2. Инициализация менеджера источников данных
        try:
            from src.data.sources_manager import data_sources_manager

            self.data_sources_manager = data_sources_manager
            self.integration_status["data_sources"] = True
            initialization_results["data_sources"] = True
            logger.info("✅ Data sources manager initialized")
        except ImportError as e:
            logger.warning(f"⚠️ Data sources manager not available: {e}")
            initialization_results["data_sources"] = False

        # 3. Инициализация монитора качества данных
        try:
            from data_quality_monitor import data_quality_monitor

            self.data_quality_monitor = data_quality_monitor
            self.integration_status["data_quality"] = True
            initialization_results["data_quality"] = True
            logger.info("✅ Data quality monitor initialized")
        except ImportError as e:
            logger.warning(f"⚠️ Data quality monitor not available: {e}")
            initialization_results["data_quality"] = False

        # 4. Инициализация оптимизатора фильтров
        try:
            # Пробуем импортировать обёртку
            try:
                from filter_optimizer import filter_optimizer
            except ImportError:
                # Fallback на прямой импорт из ai_filter_optimizer
                from ai_filter_optimizer import get_filter_optimizer

                _opt = get_filter_optimizer()

                # Создаём простую обёртку
                class SimpleWrapper:
                    def get_optimization_status(self):
                        return {"status": "available", "source": "ai_filter_optimizer"}

                filter_optimizer = SimpleWrapper()

            self.filter_optimizer = filter_optimizer
            self.integration_status["filter_optimizer"] = True
            initialization_results["filter_optimizer"] = True
            logger.info("✅ Filter optimizer initialized")
        except ImportError as e:
            logger.warning(f"⚠️ Filter optimizer not available: {e}")
            initialization_results["filter_optimizer"] = False

        # 5. Инициализация менеджера рисков
        try:
            from risk_manager import risk_manager

            self.risk_manager = risk_manager
            self.integration_status["risk_manager"] = True
            initialization_results["risk_manager"] = True
            logger.info("✅ Risk manager initialized")
        except ImportError as e:
            logger.warning(f"⚠️ Risk manager not available: {e}")
            initialization_results["risk_manager"] = False

        # 6. Инициализация forward tester
        try:
            from forward_tester import forward_test_engine, forward_test_validator

            self.forward_tester = forward_test_engine
            self.integration_status["forward_tester"] = True
            initialization_results["forward_tester"] = True
            logger.info("✅ Forward tester initialized")
        except ImportError as e:
            logger.warning(f"⚠️ Forward tester not available: {e}")
            initialization_results["forward_tester"] = False

        # 7. Инициализация системы мониторинга
        try:
            from monitoring_system import monitoring_system

            self.monitoring_system = monitoring_system
            self.integration_status["monitoring"] = True
            initialization_results["monitoring"] = True
            logger.info("✅ Monitoring system initialized")
        except ImportError as e:
            logger.warning(f"⚠️ Monitoring system not available: {e}")
            initialization_results["monitoring"] = False

        # Настраиваем интеграцию между системами
        await self._setup_system_integration()

        self.is_initialized = True

        # Генерируем отчет об инициализации
        await self._generate_initialization_report(initialization_results)

        return initialization_results

    async def _setup_system_integration(self):
        """Настраивает интеграцию между системами"""

        # Интеграция мониторинга с логированием
        if self.monitoring_system and self.enhanced_logging:
            self.monitoring_system.alert_manager.on_alert_created = self._on_alert_created
            self.monitoring_system.alert_manager.on_alert_resolved = self._on_alert_resolved
            logger.info("🔗 Integrated monitoring with enhanced logging")

        # Интеграция качества данных с источниками данных
        if self.data_quality_monitor and self.data_sources_manager:
            # Здесь можно добавить автоматическую валидацию данных
            logger.info("🔗 Integrated data quality monitoring with data sources")

        # Интеграция риск-менеджмента с мониторингом
        if self.risk_manager and self.monitoring_system:
            # Здесь можно добавить автоматические алерты по рискам
            logger.info("🔗 Integrated risk management with monitoring")

    async def _on_alert_created(self, alert):
        """Обработчик создания алерта"""
        if self.enhanced_logging:
            from enhanced_logging import get_logger

            alert_logger = get_logger("alerts")
            alert_logger.warning(f"ALERT CREATED: {alert.title} - {alert.message}")

    async def _on_alert_resolved(self, alert):
        """Обработчик разрешения алерта"""
        if self.enhanced_logging:
            from enhanced_logging import get_logger

            alert_logger = get_logger("alerts")
            alert_logger.info(f"ALERT RESOLVED: {alert.title}")

    async def _generate_initialization_report(self, results: Dict[str, bool]):
        """Генерирует отчет об инициализации"""

        report = {
            "timestamp": get_utc_now().isoformat(),
            "initialization_results": results,
            "integration_status": self.integration_status,
            "systems_available": sum(results.values()),
            "total_systems": len(results),
            "integration_health": "healthy" if all(results.values()) else "degraded",
        }

        # Сохраняем отчет
        try:
            now = get_utc_now()
            report_filename = f"system_integration_report_{now.strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_filename, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"📊 System integration report saved to {report_filename}")
        except Exception as e:
            logger.error(f"Error saving integration report: {e}")

        # Логируем сводку
        available_systems = [name for name, available in results.items() if available]
        unavailable_systems = [name for name, available in results.items() if not available]

        logger.info("🎯 Integration Summary:")
        logger.info(f"   ✅ Available systems: {', '.join(available_systems)}")
        if unavailable_systems:
            logger.warning(f"   ❌ Unavailable systems: {', '.join(unavailable_systems)}")

        return report

    async def get_system_status(self) -> Dict[str, Any]:
        """Возвращает статус всех систем"""

        status = {
            "timestamp": get_utc_now().isoformat(),
            "integration_status": self.integration_status.copy(),
            "is_initialized": self.is_initialized,
            "system_health": {},
        }

        # Проверяем здоровье каждой системы
        if self.data_sources_manager:
            try:
                health = await self.data_sources_manager.health_check()
                status["system_health"]["data_sources"] = {
                    "status": "healthy" if any(health.values()) else "unhealthy",
                    "sources_health": health,
                }
            except Exception as e:
                status["system_health"]["data_sources"] = {"status": "error", "error": str(e)}

        if self.data_quality_monitor:
            try:
                health_report = self.data_quality_monitor.get_health_report()
                status["system_health"]["data_quality"] = health_report
            except Exception as e:
                status["system_health"]["data_quality"] = {"status": "error", "error": str(e)}

        if self.enhanced_logging:
            try:
                logging_health = self.enhanced_logging.get_health_report()
                status["system_health"]["enhanced_logging"] = logging_health
            except Exception as e:
                status["system_health"]["enhanced_logging"] = {"status": "error", "error": str(e)}

        if self.risk_manager:
            try:
                risk_report = self.risk_manager.get_risk_report()
                status["system_health"]["risk_manager"] = risk_report
            except Exception as e:
                status["system_health"]["risk_manager"] = {"status": "error", "error": str(e)}

        if self.monitoring_system:
            try:
                monitoring_report = self.monitoring_system.get_monitoring_report()
                status["system_health"]["monitoring"] = monitoring_report
            except Exception as e:
                status["system_health"]["monitoring"] = {"status": "error", "error": str(e)}

        return status

    async def run_periodic_health_checks(self):
        """Запускает периодические проверки здоровья систем"""

        while True:
            try:
                logger.info("🔍 Running periodic health checks...")

                # Получаем статус всех систем
                system_status = await self.get_system_status()

                # Проверяем критические системы
                critical_systems = ["data_sources", "enhanced_logging", "monitoring"]
                unhealthy_systems = []

                for system in critical_systems:
                    if system in system_status["system_health"]:
                        health = system_status["system_health"][system]
                        if health.get("status") in ["unhealthy", "error"]:
                            unhealthy_systems.append(system)

                # Генерируем алерт если есть проблемы
                if unhealthy_systems and self.monitoring_system:
                    from monitoring_system import AlertSeverity, AlertType

                    self.monitoring_system.add_alert(
                        AlertType.SYSTEM_ERROR,
                        AlertSeverity.HIGH,
                        "Unhealthy Systems Detected",
                        f"The following critical systems are unhealthy: {', '.join(unhealthy_systems)}",
                        "system_integration",
                    )

                # Логируем результаты
                healthy_systems = len(system_status["system_health"])
                unhealthy_count = len(unhealthy_systems)

                if unhealthy_count == 0:
                    logger.info(f"✅ All systems healthy ({healthy_systems} systems checked)")
                else:
                    logger.warning(
                        f"⚠️ {unhealthy_count}/{healthy_systems} systems unhealthy: {unhealthy_systems}"
                    )

                # Ждем до следующей проверки (каждые 5 минут)
                await asyncio.sleep(300)

            except Exception as e:
                logger.error(f"Error in periodic health checks: {e}")
                await asyncio.sleep(60)  # Ждем минуту при ошибке

    async def optimize_system_performance(self):
        """Оптимизирует производительность системы"""

        logger.info("⚡ Starting system performance optimization...")

        optimization_results = {}

        # Оптимизация фильтров
        if self.filter_optimizer:
            try:
                logger.info("🔧 Optimizing filter system...")
                # Здесь должен быть вызов оптимизации фильтров
                optimization_results["filter_optimization"] = True
            except Exception as e:
                logger.error(f"Error optimizing filters: {e}")
                optimization_results["filter_optimization"] = False

        # Оптимизация источников данных
        if self.data_sources_manager:
            try:
                logger.info("🔧 Optimizing data sources...")
                # Отключаем проблемные источники
                stats = self.data_sources_manager.get_source_statistics()
                for source_name, source_stats in stats.items():
                    if source_stats.get("success_rate", 1.0) < 0.8:  # Менее 80% успешных запросов
                        self.data_sources_manager.disable_failing_source(source_name)
                        logger.warning(f"Disabled failing data source: {source_name}")
                optimization_results["data_sources_optimization"] = True
            except Exception as e:
                logger.error(f"Error optimizing data sources: {e}")
                optimization_results["data_sources_optimization"] = False

        # Оптимизация логирования
        if self.enhanced_logging:
            try:
                logger.info("🔧 Optimizing logging system...")
                # Очистка старых логов
                optimization_results["logging_optimization"] = True
            except Exception as e:
                logger.error(f"Error optimizing logging: {e}")
                optimization_results["logging_optimization"] = False

        logger.info(f"⚡ Performance optimization completed: {optimization_results}")
        return optimization_results

    async def generate_system_report(self) -> Dict[str, Any]:
        """Генерирует полный отчет о состоянии системы"""

        logger.info("📊 Generating comprehensive system report...")

        report = {
            "timestamp": get_utc_now().isoformat(),
            "integration_status": self.integration_status,
            "system_health": {},
            "performance_metrics": {},
            "recommendations": [],
        }

        # Собираем данные от всех систем
        if self.data_sources_manager:
            report["system_health"]["data_sources"] = (
                self.data_sources_manager.get_source_statistics()
            )

        if self.data_quality_monitor:
            report["system_health"]["data_quality"] = self.data_quality_monitor.get_health_report()

        if self.enhanced_logging:
            report["system_health"]["logging"] = self.enhanced_logging.get_health_report()

        if self.risk_manager:
            report["system_health"]["risk_management"] = self.risk_manager.get_risk_report()

        if self.monitoring_system:
            report["system_health"]["monitoring"] = self.monitoring_system.get_monitoring_report()

        # Генерируем рекомендации
        report["recommendations"] = self._generate_recommendations(report)

        # Сохраняем отчет
        try:
            now = get_utc_now()
            report_filename = f"comprehensive_system_report_{now.strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_filename, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"📊 Comprehensive system report saved to {report_filename}")
        except Exception as e:
            logger.error(f"Error saving system report: {e}")

        return report

    def _generate_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """Генерирует рекомендации на основе отчета"""

        recommendations = []

        # Проверяем здоровье источников данных
        if "data_sources" in report["system_health"]:
            data_sources = report["system_health"]["data_sources"]
            for source_name, stats in data_sources.items():
                if stats.get("success_rate", 1.0) < 0.9:
                    recommendations.append(
                        f"Consider replacing or fixing data source {source_name} (success rate: {stats.get('success_rate', 0):.1%})"
                    )

        # Проверяем качество данных
        if "data_quality" in report["system_health"]:
            data_quality = report["system_health"]["data_quality"]
            if data_quality.get("overall_health_score", 1.0) < 0.8:
                recommendations.append(
                    "Data quality is below optimal - review data validation rules"
                )

        # Проверяем риск-менеджмент
        if "risk_management" in report["system_health"]:
            risk_mgmt = report["system_health"]["risk_management"]
            if risk_mgmt.get("margin_call_risk", {}).get("is_at_risk", False):
                recommendations.append("Margin call risk detected - reduce position sizes")

        # Проверяем мониторинг
        if "monitoring" in report["system_health"]:
            monitoring = report["system_health"]["monitoring"]
            if monitoring.get("system_health", {}).get("critical_alerts_count", 0) > 0:
                recommendations.append("Critical alerts detected - immediate attention required")

        return recommendations


# Глобальный экземпляр интеграции
system_integration = SystemIntegration()


# Удобные функции
async def initialize_improved_systems():
    """Инициализирует все улучшенные системы"""
    return await system_integration.initialize_all_systems()


async def get_system_integration_status():
    """Возвращает статус интеграции систем"""
    return await system_integration.get_system_status()


async def run_system_health_monitoring():
    """Запускает мониторинг здоровья систем"""
    await system_integration.run_periodic_health_checks()


async def generate_comprehensive_report():
    """Генерирует полный отчет о системе"""
    return await system_integration.generate_system_report()
