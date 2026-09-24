#!/usr/bin/env python3
"""
Скрипт для просмотра статуса агентов и всех систем улучшений.

Показывает:
- Рейтинги и менторство
- KPI и достижения
- Аномалии и предупреждения
- Активные задачи
- A/B тесты
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from observability.agent_improvements_integration import get_agent_improvements_integration

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    integration = get_agent_improvements_integration()

    agents = ["signal_live", "auto_execution", "risk_monitor"]

    logger.info("\n" + "=" * 80)
    logger.info("📊 СТАТУС АГЕНТОВ И СИСТЕМ УЛУЧШЕНИЙ")
    logger.info("=" * 80 + "\n")

    for agent in agents:
        status = integration.get_agent_status(agent)

        # TODO: Convert f-string to %s formatting for performance
        logger.info(f"\n🤖 АГЕНТ: {agent}")
        logger.info("-" * 80)

        # Менторство
        if status.get("mentorship"):
            mentorship = status["mentorship"]
            logger.info("👥 Менторство:")
            # TODO: Convert f-string to %s formatting for performance
            logger.info(f"   Уровень: {mentorship.get('mentor_level', 'N/A')}")
            # TODO: Convert f-string to %s formatting for performance
            logger.info(f"   Success Rate: {mentorship.get('success_rate', 0):.2%}")
            # TODO: Convert f-string to %s formatting for performance
            logger.info(f"   Всего задач: {mentorship.get('total_tasks', 0)}")
            if mentorship.get("mentor"):
                # TODO: Convert f-string to %s formatting for performance
                logger.info(f"   Ментор: {mentorship['mentor']}")

        # KPI
        if status.get("kpi"):
            kpi = status["kpi"]
            logger.info("\n📊 KPI:")
            # TODO: Convert f-string to %s formatting for performance
            logger.info(f"   Общий балл: {kpi.get('overall_score', 0):.1f}/100")
            if kpi.get("achievements"):
                # TODO: Convert f-string to %s formatting for performance
                logger.info(f"   Достижения: {', '.join(kpi['achievements'])}")
            if kpi.get("kpis"):
                logger.info("   Метрики:")
                for kpi_item in kpi["kpis"]:
                    status_emoji = (
                        "✅"
                        if kpi_item["status"] == "normal"
                        else "⚠️"
                        if kpi_item["status"] == "warning"
                        else "❌"
                    )
                    logger.info(
                        f"     {status_emoji} {kpi_item['name']}: {kpi_item['current']:.2f} / {kpi_item['target']:.2f} ({kpi_item['status']})"
                    )

        # Аномалии
        if status.get("anomalies"):
            # TODO: Convert f-string to %s formatting for performance
            logger.info(f"\n⚠️ Аномалии ({len(status['anomalies'])}):")
            for anomaly in status["anomalies"][:3]:
                # TODO: Convert f-string to %s formatting for performance
                logger.info(f"   - {anomaly['description']} (severity: {anomaly['severity']})")

        # Предупреждения
        if status.get("warnings"):
            # TODO: Convert f-string to %s formatting for performance
            logger.info(f"\n🔔 Предупреждения ({len(status['warnings'])}):")
            for warning in status["warnings"][:3]:
                # TODO: Convert f-string to %s formatting for performance
                logger.info(f"   - {warning['message']}")

        # Задачи
        if status.get("tasks"):
            # TODO: Convert f-string to %s formatting for performance
            logger.info(f"\n📋 Задачи ({len(status['tasks'])}):")
            for task in status["tasks"][:3]:
                logger.info(
                    f"   - {task['title']} (приоритет: {task['priority']}, статус: {task['status']})"
                )

        logger.info()

    logger.info("=" * 80 + "\n")


if __name__ == "__main__":
    main()
