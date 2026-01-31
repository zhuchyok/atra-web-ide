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
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    integration = get_agent_improvements_integration()
    
    agents = ["signal_live", "auto_execution", "risk_monitor"]
    
    print("\n" + "="*80)
    print("📊 СТАТУС АГЕНТОВ И СИСТЕМ УЛУЧШЕНИЙ")
    print("="*80 + "\n")
    
    for agent in agents:
        status = integration.get_agent_status(agent)
        
        print(f"\n🤖 АГЕНТ: {agent}")
        print("-" * 80)
        
        # Менторство
        if status.get("mentorship"):
            mentorship = status["mentorship"]
            print(f"👥 Менторство:")
            print(f"   Уровень: {mentorship.get('mentor_level', 'N/A')}")
            print(f"   Success Rate: {mentorship.get('success_rate', 0):.2%}")
            print(f"   Всего задач: {mentorship.get('total_tasks', 0)}")
            if mentorship.get("mentor"):
                print(f"   Ментор: {mentorship['mentor']}")
        
        # KPI
        if status.get("kpi"):
            kpi = status["kpi"]
            print(f"\n📊 KPI:")
            print(f"   Общий балл: {kpi.get('overall_score', 0):.1f}/100")
            if kpi.get("achievements"):
                print(f"   Достижения: {', '.join(kpi['achievements'])}")
            if kpi.get("kpis"):
                print(f"   Метрики:")
                for kpi_item in kpi["kpis"]:
                    status_emoji = "✅" if kpi_item["status"] == "normal" else "⚠️" if kpi_item["status"] == "warning" else "❌"
                    print(f"     {status_emoji} {kpi_item['name']}: {kpi_item['current']:.2f} / {kpi_item['target']:.2f} ({kpi_item['status']})")
        
        # Аномалии
        if status.get("anomalies"):
            print(f"\n⚠️ Аномалии ({len(status['anomalies'])}):")
            for anomaly in status["anomalies"][:3]:
                print(f"   - {anomaly['description']} (severity: {anomaly['severity']})")
        
        # Предупреждения
        if status.get("warnings"):
            print(f"\n🔔 Предупреждения ({len(status['warnings'])}):")
            for warning in status["warnings"][:3]:
                print(f"   - {warning['message']}")
        
        # Задачи
        if status.get("tasks"):
            print(f"\n📋 Задачи ({len(status['tasks'])}):")
            for task in status["tasks"][:3]:
                print(f"   - {task['title']} (приоритет: {task['priority']}, статус: {task['status']})")
        
        print()
    
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

