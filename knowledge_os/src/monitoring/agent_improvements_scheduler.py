"""
Периодический запуск всех систем улучшений агентов.

Объединяет все системы: менторство, A/B тестирование, приоритизацию,
обнаружение аномалий, раннее предупреждение, командную работу, KPI, документацию.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from observability.agent_improvements_integration import get_agent_improvements_integration
from observability.mentorship import get_mentorship_system
from observability.ab_testing import get_ab_testing_system
from observability.task_prioritizer import get_task_prioritizer
from observability.anomaly_detector import get_anomaly_detector
from observability.early_warning import get_early_warning_system
from observability.team_work import get_team_work_system
from observability.kpi_system import get_kpi_system
from observability.auto_documentation import get_auto_documentation_system

logger = logging.getLogger(__name__)


async def run_agent_improvements_scheduler():
    """
    Периодически запускает все системы улучшений агентов.
    
    Запускается каждые 6 часов для:
    1. Обновления рейтингов и назначения менторов
    2. Анализа A/B тестов
    3. Приоритизации и распределения задач
    4. Обнаружения аномалий
    5. Анализа трендов для раннего предупреждения
    6. Обновления KPI
    7. Генерации документации
    """
    logger.info("🔄 Запуск планировщика улучшений агентов")
    
    integration = get_agent_improvements_integration()
    
    while True:
        try:
            # Ждем 6 часов
            await asyncio.sleep(6 * 60 * 60)  # 6 часов
            
            logger.info("🧠 Запуск всех систем улучшений агентов...")
            
            # 1. Обновление менторства
            try:
                logger.info("👥 Обновление системы менторства...")
                mentorship = get_mentorship_system()
                # Автоматически назначаем менторов для младших агентов
                mentees = mentorship.get_mentees(max_level=2)
                for mentee_rating in mentees:
                    mentorship.assign_mentor(mentee_rating.agent)
                logger.info("✅ Система менторства обновлена")
            except Exception as e:
                logger.error("❌ Ошибка обновления менторства: %s", e, exc_info=True)
            
            # 2. Анализ A/B тестов
            try:
                logger.info("🧪 Анализ A/B тестов...")
                ab_system = get_ab_testing_system()
                # Проверяем активные тесты и завершаем готовые
                for test_id in list(ab_system._active_tests.keys()):
                    test = ab_system._load_test(test_id)
                    if test:
                        # Проверяем, достигли ли минимального размера выборки
                        all_ready = all(
                            r.sample_size >= test.min_sample_size
                            for r in test.results
                        )
                        if all_ready:
                            winner = ab_system.complete_test(test_id)
                            if winner:
                                logger.info("🏆 A/B тест завершен, победитель: %s", winner)
                logger.info("✅ A/B тесты проанализированы")
            except Exception as e:
                logger.error("❌ Ошибка анализа A/B тестов: %s", e, exc_info=True)
            
            # 3. Приоритизация задач
            try:
                logger.info("📋 Приоритизация задач...")
                prioritizer = get_task_prioritizer()
                prioritized = prioritizer.prioritize_tasks()
                logger.info("✅ Приоритизировано %d задач", len(prioritized))
            except Exception as e:
                logger.error("❌ Ошибка приоритизации задач: %s", e, exc_info=True)
            
            # 4. Обнаружение аномалий
            try:
                logger.info("🔍 Обнаружение аномалий...")
                detector = get_anomaly_detector()
                # Проверяем всех агентов
                agents = ["signal_live", "auto_execution", "risk_monitor"]
                total_anomalies = 0
                for agent in agents:
                    anomalies = detector.detect_anomalies(agent)
                    total_anomalies += len(anomalies)
                    if anomalies:
                        for anomaly in anomalies:
                            logger.warning("⚠️ Аномалия для %s: %s", agent, anomaly.description)
                logger.info("✅ Обнаружено %d аномалий", total_anomalies)
            except Exception as e:
                logger.error("❌ Ошибка обнаружения аномалий: %s", e, exc_info=True)
            
            # 5. Раннее предупреждение
            try:
                logger.info("🔔 Анализ трендов для раннего предупреждения...")
                warning_system = get_early_warning_system()
                agents = ["signal_live", "auto_execution", "risk_monitor"]
                total_warnings = 0
                for agent in agents:
                    warnings = warning_system.analyze_trends(agent)
                    total_warnings += len(warnings)
                    if warnings:
                        for warning in warnings:
                            logger.warning("🔔 Предупреждение для %s: %s", agent, warning.message)
                logger.info("✅ Сгенерировано %d предупреждений", total_warnings)
            except Exception as e:
                logger.error("❌ Ошибка раннего предупреждения: %s", e, exc_info=True)
            
            # 6. Обновление KPI
            try:
                logger.info("📊 Обновление KPI...")
                kpi_system = get_kpi_system()
                top_agents = kpi_system.get_top_agents(limit=3)
                if top_agents:
                    logger.info("🏆 Топ агенты: %s", 
                               ", ".join(f"{a.agent} ({a.overall_score:.1f})" for a in top_agents))
                logger.info("✅ KPI обновлены")
            except Exception as e:
                logger.error("❌ Ошибка обновления KPI: %s", e, exc_info=True)
            
            # 7. Генерация документации (реже - раз в день)
            current_hour = datetime.now(timezone.utc).hour
            if current_hour == 3:  # В 3:00 UTC
                try:
                    logger.info("📝 Генерация документации...")
                    doc_system = get_auto_documentation_system()
                    # Генерируем отчеты о работе агентов
                    kpi_system = get_kpi_system()
                    all_kpis = kpi_system.get_all_kpis()
                    for agent, kpi in all_kpis.items():
                        sections = {
                            "KPI": f"Общий балл: {kpi.overall_score:.1f}",
                            "Достижения": ", ".join(kpi.achievements) if kpi.achievements else "Нет",
                        }
                        doc_system.generate_report(f"{agent} Status Report", sections, agent)
                    logger.info("✅ Документация сгенерирована")
                except Exception as e:
                    logger.error("❌ Ошибка генерации документации: %s", e, exc_info=True)
            
            logger.info("✅ Все системы улучшений обновлены")
            
        except asyncio.CancelledError:
            logger.info("🛑 Планировщик улучшений агентов остановлен")
            break
        except Exception as e:
            logger.error("❌ Критическая ошибка в планировщике: %s", e, exc_info=True)
            # Ждем 1 час перед повторной попыткой
            await asyncio.sleep(60 * 60)


async def run_agent_improvements_scheduler_task():
    """Обертка для запуска планировщика как задачи"""
    await run_agent_improvements_scheduler()

