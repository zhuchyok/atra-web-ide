#!/usr/bin/env python3
"""
Пример использования системы мультипроектности.

Демонстрирует работу агентов с несколькими проектами.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from observability.project_manager import get_project_manager
from observability.project_context import project_context
from observability.multi_project_integration import get_multi_project_integration
from observability.multi_project_knowledge import get_multi_project_knowledge


def main():
    print("\n" + "="*80)
    print("🌐 ПРИМЕР ИСПОЛЬЗОВАНИЯ СИСТЕМЫ МУЛЬТИПРОЕКТНОСТИ")
    print("="*80 + "\n")
    
    manager = get_project_manager()
    integration = get_multi_project_integration()
    knowledge = get_multi_project_knowledge()
    
    # 1. Создаем проекты
    print("📁 Шаг 1: Создание проектов...")
    
    project1 = manager.create_project(
        name="ATRA Trading",
        description="Алгоритмическая торговля на крипторынке",
        capabilities_required=["ml", "analysis", "trading"],
    )
    print(f"   ✅ Создан проект: {project1.name} ({project1.project_id})")
    
    project2 = manager.create_project(
        name="New Trading Bot",
        description="Новый торговый бот для другого рынка",
        capabilities_required=["ml", "analysis", "trading"],
    )
    print(f"   ✅ Создан проект: {project2.name} ({project2.project_id})")
    
    # 2. Назначаем агентов
    print("\n👥 Шаг 2: Назначение агентов...")
    
    manager.assign_agent_to_project(
        agent="signal_live",
        project_id=project1.project_id,
        role="Data Analyst",
        capabilities=["ml", "analysis", "signals"],
    )
    print(f"   ✅ signal_live назначен на {project1.name}")
    
    manager.assign_agent_to_project(
        agent="signal_live",
        project_id=project2.project_id,
        role="Data Analyst",
        capabilities=["ml", "analysis", "signals"],
    )
    print(f"   ✅ signal_live назначен на {project2.name}")
    
    # 3. Работа в контексте проекта 1
    print("\n🔄 Шаг 3: Работа в контексте проекта 1...")
    with project_context(project1.project_id):
        integration.process_agent_activity_for_project(
            project_id=project1.project_id,
            agent="signal_live",
            role="Data Analyst",
            activity_type="signal_generated",
            success=True,
            metrics={"win_rate": 0.75, "profit_factor": 2.0},
        )
        print(f"   ✅ Активность обработана для {project1.name}")
    
    # 4. Работа в контексте проекта 2
    print("\n🔄 Шаг 4: Работа в контексте проекта 2...")
    with project_context(project2.project_id):
        integration.process_agent_activity_for_project(
            project_id=project2.project_id,
            agent="signal_live",
            role="Data Analyst",
            activity_type="signal_generated",
            success=True,
            metrics={"win_rate": 0.70, "profit_factor": 1.8},
        )
        print(f"   ✅ Активность обработана для {project2.name}")
    
    # 5. Обмен знаниями
    print("\n🔄 Шаг 5: Обмен знаниями между проектами...")
    knowledge.share_knowledge_between_projects(
        source_project_id=project1.project_id,
        target_project_id=project2.project_id,
        knowledge_items=[
            "ML модель с ROC AUC 1.0 работает отлично",
            "Оптимальные параметры фильтров: ML 0.40/0.50",
        ],
    )
    print(f"   ✅ Знания переданы от {project1.name} к {project2.name}")
    
    # 6. Статус проектов
    print("\n📊 Шаг 6: Статус проектов...")
    for project in [project1, project2]:
        context = manager.get_project_context(project.project_id)
        print(f"\n   📁 {project.name}:")
        print(f"      Агентов: {len(context['assignments'])}")
        for assignment in context['assignments']:
            print(f"        - {assignment['agent']} ({assignment['role']})")
    
    print("\n" + "="*80)
    print("✅ ПРИМЕР ЗАВЕРШЕН!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

