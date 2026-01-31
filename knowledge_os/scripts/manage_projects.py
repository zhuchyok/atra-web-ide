#!/usr/bin/env python3
"""
Управление проектами для агентов-сотрудников.

Создание проектов, назначение агентов, переключение между проектами.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from observability.project_manager import get_project_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Управление проектами")
    subparsers = parser.add_subparsers(dest='command', help='Команды')
    
    # Создать проект
    create_parser = subparsers.add_parser('create', help='Создать проект')
    create_parser.add_argument('--name', required=True, help='Название проекта')
    create_parser.add_argument('--description', required=True, help='Описание проекта')
    create_parser.add_argument('--capabilities', nargs='+', help='Требуемые возможности')
    
    # Назначить агента
    assign_parser = subparsers.add_parser('assign', help='Назначить агента на проект')
    assign_parser.add_argument('--project-id', required=True, help='ID проекта')
    assign_parser.add_argument('--agent', required=True, help='Имя агента')
    assign_parser.add_argument('--role', required=True, help='Роль агента')
    assign_parser.add_argument('--capabilities', nargs='+', required=True, help='Возможности агента')
    
    # Переключить проект
    switch_parser = subparsers.add_parser('switch', help='Переключить текущий проект')
    switch_parser.add_argument('--project-id', required=True, help='ID проекта')
    
    # Список проектов
    list_parser = subparsers.add_parser('list', help='Список проектов')
    list_parser.add_argument('--agent', help='Фильтр по агенту')
    
    # Статус проекта
    status_parser = subparsers.add_parser('status', help='Статус проекта')
    status_parser.add_argument('--project-id', help='ID проекта (если не указан - текущий)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    manager = get_project_manager()
    
    if args.command == 'create':
        project = manager.create_project(
            name=args.name,
            description=args.description,
            capabilities_required=args.capabilities,
        )
        print(f"✅ Проект создан: {project.project_id}")
        print(f"   Название: {project.name}")
        return 0
    
    elif args.command == 'assign':
        success = manager.assign_agent_to_project(
            agent=args.agent,
            project_id=args.project_id,
            role=args.role,
            capabilities=args.capabilities,
        )
        if success:
            print(f"✅ Агент {args.agent} назначен на проект {args.project_id}")
        else:
            print(f"❌ Ошибка назначения агента")
        return 0 if success else 1
    
    elif args.command == 'switch':
        success = manager.set_current_project(args.project_id)
        if success:
            project = manager.get_current_project()
            print(f"✅ Переключено на проект: {project.name} ({args.project_id})")
        else:
            print(f"❌ Проект не найден: {args.project_id}")
        return 0 if success else 1
    
    elif args.command == 'list':
        if args.agent:
            projects = manager.get_agent_projects(args.agent)
            print(f"\n📁 Проекты агента {args.agent}:")
            for project in projects:
                print(f"  - {project.name} ({project.project_id}) - {project.status.value}")
        else:
            print("\n📁 Все проекты:")
            for project in manager._projects.values():
                print(f"  - {project.name} ({project.project_id}) - {project.status.value}")
        return 0
    
    elif args.command == 'status':
        if args.project_id:
            project_id = args.project_id
        else:
            current = manager.get_current_project()
            if not current:
                print("❌ Нет активного проекта")
                return 1
            project_id = current.project_id
        
        context = manager.get_project_context(project_id)
        print(f"\n📊 Статус проекта: {context['name']}")
        print(f"   ID: {context['project_id']}")
        print(f"   Статус: {context['status']}")
        print(f"   Агентов: {len(context['assignments'])}")
        for assignment in context['assignments']:
            print(f"     - {assignment['agent']} ({assignment['role']})")
        return 0
    
    return 1


if __name__ == "__main__":
    sys.exit(main())

