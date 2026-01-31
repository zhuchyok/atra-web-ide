"""
Hierarchical Orchestration - Иерархическая оркестрация с визуализацией
Основано на OrchVis (2025) и AgentOrchestra: human-centered, transparent visualization
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Статус задачи"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class HierarchicalGoal:
    """Иерархическая цель"""
    goal_id: str
    description: str
    level: int  # 0 = root, 1 = department, 2 = expert
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    assigned_to: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    verification: Optional[Dict] = None


@dataclass
class AgentDependency:
    """Зависимость между агентами"""
    from_agent: str
    to_agent: str
    dependency_type: str  # "blocks", "requires", "informs"
    description: str


@dataclass
class OrchestrationState:
    """Состояние оркестрации"""
    goals: Dict[str, HierarchicalGoal] = field(default_factory=dict)
    dependencies: List[AgentDependency] = field(default_factory=list)
    execution_log: List[Dict] = field(default_factory=list)
    visualization_data: Dict = field(default_factory=dict)


class HierarchicalOrchestrator:
    """
    Hierarchical Orchestrator - иерархическая оркестрация с визуализацией
    
    Компоненты (OrchVis-style):
    1. Hierarchical goal alignment
    2. Task assignment
    3. Conflict resolution
    4. Transparent visualization
    5. Automated verification
    6. Inter-agent dependencies tracking
    """
    
    def __init__(self, root_agent: str = "Victoria"):
        self.root_agent = root_agent
        self.state = OrchestrationState()
        self.agents: Dict[str, Dict] = {}  # agent_name -> capabilities
    
    async def orchestrate(
        self,
        user_intent: str,
        agents: Dict[str, Dict]
    ) -> OrchestrationState:
        """
        Оркестрировать выполнение задачи
        
        Args:
            user_intent: Намерение пользователя
            agents: Словарь агентов и их возможностей
        
        Returns:
            Состояние оркестрации
        """
        logger.info(f"🎯 Hierarchical Orchestration: {user_intent[:80]}")
        
        self.agents = agents
        
        # 1. Декомпозиция на иерархические цели
        goals = await self._decompose_goals(user_intent)
        
        # 2. Выравнивание целей (goal alignment)
        aligned_goals = await self._align_goals(goals)
        
        # 3. Назначение задач (task assignment)
        assigned_goals = await self._assign_tasks(aligned_goals)
        
        # 4. Отслеживание зависимостей
        dependencies = await self._track_dependencies(assigned_goals)
        
        # 5. Мониторинг выполнения
        execution_log = await self._monitor_execution(assigned_goals)
        
        # 6. Автоматическая верификация
        verification_results = await self._verify_execution(assigned_goals, execution_log)
        
        # 7. Генерация данных для визуализации
        visualization_data = self._generate_visualization_data(
            assigned_goals, dependencies, execution_log, verification_results
        )
        
        self.state = OrchestrationState(
            goals={g.goal_id: g for g in assigned_goals},
            dependencies=dependencies,
            execution_log=execution_log,
            visualization_data=visualization_data
        )
        
        return self.state
    
    async def _decompose_goals(self, user_intent: str) -> List[HierarchicalGoal]:
        """Декомпозировать намерение на иерархические цели"""
        import uuid
        
        # Строим промпт для декомпозиции
        prompt = f"""Разбей следующее намерение на иерархические цели:

НАМЕРЕНИЕ: {user_intent}

Создай структуру целей:
- Уровень 0 (root): Главная цель
- Уровень 1 (department): Цели для отделов/групп экспертов
- Уровень 2 (expert): Конкретные задачи для экспертов

ФОРМАТ:
0. [Главная цель]
   1.1. [Цель отдела 1]
      1.1.1. [Задача эксперта 1]
      1.1.2. [Задача эксперта 2]
   1.2. [Цель отдела 2]
      1.2.1. [Задача эксперта 3]

ИЕРАРХИЧЕСКИЕ ЦЕЛИ:"""
        
        # TODO: Генерация через модель
        # Пока упрощенная структура
        root_goal = HierarchicalGoal(
            goal_id=str(uuid.uuid4()),
            description=user_intent,
            level=0
        )
        
        # Пример декомпозиции
        dept_goals = [
            HierarchicalGoal(
                goal_id=str(uuid.uuid4()),
                description=f"Подзадача {i+1}",
                level=1,
                parent_id=root_goal.goal_id
            )
            for i in range(3)
        ]
        
        root_goal.children = [g.goal_id for g in dept_goals]
        
        expert_goals = []
        for dept_goal in dept_goals:
            expert_goals.extend([
                HierarchicalGoal(
                    goal_id=str(uuid.uuid4()),
                    description=f"Экспертная задача {j+1}",
                    level=2,
                    parent_id=dept_goal.goal_id
                )
                for j in range(2)
            ])
            dept_goal.children = [g.goal_id for g in expert_goals[-2:]]
        
        return [root_goal] + dept_goals + expert_goals
    
    async def _align_goals(self, goals: List[HierarchicalGoal]) -> List[HierarchicalGoal]:
        """Выровнять цели (goal alignment)"""
        # Проверяем согласованность целей
        for goal in goals:
            if goal.parent_id:
                parent = next((g for g in goals if g.goal_id == goal.parent_id), None)
                if parent:
                    # Проверяем, что цель согласована с родителем
                    if not self._check_goal_alignment(goal, parent):
                        logger.warning(f"⚠️ Цель {goal.goal_id} не выровнена с родителем")
                        # Корректируем
                        goal.description = f"{parent.description} → {goal.description}"
        
        return goals
    
    def _check_goal_alignment(self, goal: HierarchicalGoal, parent: HierarchicalGoal) -> bool:
        """Проверить выравнивание цели с родителем"""
        # Простая проверка: цель должна быть связана с родителем
        return goal.parent_id == parent.goal_id
    
    async def _assign_tasks(self, goals: List[HierarchicalGoal]) -> List[HierarchicalGoal]:
        """Назначить задачи агентам (task assignment)"""
        # Назначаем задачи на основе возможностей агентов
        for goal in goals:
            if goal.level == 0:
                # Root задача - Victoria
                goal.assigned_to = self.root_agent
            elif goal.level == 1:
                # Department задачи - выбираем по домену
                goal.assigned_to = self._select_agent_for_department(goal)
            else:
                # Expert задачи - выбираем специалиста
                goal.assigned_to = self._select_agent_for_expert_task(goal)
            
            if goal.assigned_to:
                goal.status = TaskStatus.ASSIGNED
                logger.debug(f"✅ Задача {goal.goal_id} назначена {goal.assigned_to}")
        
        return goals
    
    def _select_agent_for_department(self, goal: HierarchicalGoal) -> Optional[str]:
        """Выбрать агента для department задачи"""
        # Упрощенная логика: выбираем по ключевым словам
        description_lower = goal.description.lower()
        
        if "backend" in description_lower or "api" in description_lower:
            return "Игорь"
        elif "devops" in description_lower or "deploy" in description_lower:
            return "Сергей"
        elif "ml" in description_lower or "model" in description_lower:
            return "Дмитрий"
        elif "database" in description_lower or "db" in description_lower:
            return "Роман"
        
        return "Victoria"  # Fallback
    
    def _select_agent_for_expert_task(self, goal: HierarchicalGoal) -> Optional[str]:
        """Выбрать агента для expert задачи"""
        # Аналогично department, но более детально
        return self._select_agent_for_department(goal)
    
    async def _track_dependencies(self, goals: List[HierarchicalGoal]) -> List[AgentDependency]:
        """Отслеживать зависимости между агентами"""
        dependencies = []
        
        # Находим зависимости на основе иерархии
        for goal in goals:
            if goal.parent_id:
                parent = next((g for g in goals if g.goal_id == goal.parent_id), None)
                if parent and parent.assigned_to and goal.assigned_to:
                    if parent.assigned_to != goal.assigned_to:
                        dependencies.append(AgentDependency(
                            from_agent=goal.assigned_to,
                            to_agent=parent.assigned_to,
                            dependency_type="requires",
                            description=f"Задача {goal.goal_id} требует завершения {parent.goal_id}"
                        ))
        
        # Находим блокирующие зависимости
        for goal in goals:
            if goal.dependencies:
                for dep_id in goal.dependencies:
                    dep_goal = next((g for g in goals if g.goal_id == dep_id), None)
                    if dep_goal and dep_goal.assigned_to and goal.assigned_to:
                        if dep_goal.assigned_to != goal.assigned_to:
                            dependencies.append(AgentDependency(
                                from_agent=goal.assigned_to,
                                to_agent=dep_goal.assigned_to,
                                dependency_type="blocks",
                                description=f"Задача {goal.goal_id} блокируется {dep_goal.goal_id}"
                            ))
        
        logger.info(f"📊 Найдено {len(dependencies)} зависимостей")
        
        return dependencies
    
    async def _monitor_execution(self, goals: List[HierarchicalGoal]) -> List[Dict]:
        """Мониторить выполнение (automated verification)"""
        execution_log = []
        
        for goal in goals:
            if goal.assigned_to:
                # Симуляция выполнения
                log_entry = {
                    "goal_id": goal.goal_id,
                    "assigned_to": goal.assigned_to,
                    "status": goal.status.value,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "progress": 0.0
                }
                
                # Обновляем статус
                if goal.status == TaskStatus.ASSIGNED:
                    goal.status = TaskStatus.IN_PROGRESS
                    log_entry["status"] = "in_progress"
                    log_entry["progress"] = 0.5
                
                execution_log.append(log_entry)
        
        return execution_log
    
    async def _verify_execution(
        self,
        goals: List[HierarchicalGoal],
        execution_log: List[Dict]
    ) -> Dict[str, bool]:
        """Автоматическая верификация выполнения"""
        verification_results = {}
        
        for goal in goals:
            # Простая верификация: проверяем наличие результата
            log_entry = next(
                (log for log in execution_log if log["goal_id"] == goal.goal_id),
                None
            )
            
            if log_entry and log_entry.get("progress", 0) >= 1.0:
                verification_results[goal.goal_id] = True
                goal.status = TaskStatus.COMPLETED
                goal.verification = {"verified": True, "timestamp": datetime.now(timezone.utc).isoformat()}
            else:
                verification_results[goal.goal_id] = False
        
        verified_count = sum(1 for v in verification_results.values() if v)
        logger.info(f"✅ Верифицировано: {verified_count}/{len(verification_results)}")
        
        return verification_results
    
    def _generate_visualization_data(
        self,
        goals: List[HierarchicalGoal],
        dependencies: List[AgentDependency],
        execution_log: List[Dict],
        verification_results: Dict[str, bool]
    ) -> Dict:
        """Генерировать данные для визуализации (transparent visualization)"""
        # Структура для визуализации
        visualization = {
            "hierarchy": self._build_hierarchy_tree(goals),
            "dependencies_graph": self._build_dependencies_graph(dependencies),
            "execution_timeline": execution_log,
            "verification_status": verification_results,
            "agent_workload": self._calculate_agent_workload(goals),
            "progress_summary": self._calculate_progress_summary(goals, execution_log)
        }
        
        return visualization
    
    def _build_hierarchy_tree(self, goals: List[HierarchicalGoal]) -> Dict:
        """Построить дерево иерархии"""
        tree = {}
        
        # Находим root
        root = next((g for g in goals if g.level == 0), None)
        if root:
            tree = {
                "id": root.goal_id,
                "description": root.description,
                "level": root.level,
                "status": root.status.value,
                "children": self._build_children_tree(root, goals)
            }
        
        return tree
    
    def _build_children_tree(self, parent: HierarchicalGoal, all_goals: List[HierarchicalGoal]) -> List[Dict]:
        """Построить дерево детей"""
        children = []
        
        for child_id in parent.children:
            child = next((g for g in all_goals if g.goal_id == child_id), None)
            if child:
                children.append({
                    "id": child.goal_id,
                    "description": child.description,
                    "level": child.level,
                    "status": child.status.value,
                    "assigned_to": child.assigned_to,
                    "children": self._build_children_tree(child, all_goals)
                })
        
        return children
    
    def _build_dependencies_graph(self, dependencies: List[AgentDependency]) -> Dict:
        """Построить граф зависимостей"""
        nodes = set()
        edges = []
        
        for dep in dependencies:
            nodes.add(dep.from_agent)
            nodes.add(dep.to_agent)
            edges.append({
                "from": dep.from_agent,
                "to": dep.to_agent,
                "type": dep.dependency_type,
                "description": dep.description
            })
        
        return {
            "nodes": list(nodes),
            "edges": edges
        }
    
    def _calculate_agent_workload(self, goals: List[HierarchicalGoal]) -> Dict[str, int]:
        """Рассчитать нагрузку агентов"""
        workload = {}
        
        for goal in goals:
            if goal.assigned_to:
                workload[goal.assigned_to] = workload.get(goal.assigned_to, 0) + 1
        
        return workload
    
    def _calculate_progress_summary(
        self,
        goals: List[HierarchicalGoal],
        execution_log: List[Dict]
    ) -> Dict:
        """Рассчитать сводку прогресса"""
        total = len(goals)
        completed = sum(1 for g in goals if g.status == TaskStatus.COMPLETED)
        in_progress = sum(1 for g in goals if g.status == TaskStatus.IN_PROGRESS)
        pending = sum(1 for g in goals if g.status == TaskStatus.PENDING)
        
        return {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "completion_rate": completed / total if total > 0 else 0.0
        }


async def main():
    """Пример использования"""
    orchestrator = HierarchicalOrchestrator(root_agent="Victoria")
    
    agents = {
        "Victoria": {"role": "team_lead", "capabilities": ["planning", "coordination"]},
        "Игорь": {"role": "backend", "capabilities": ["coding", "api"]},
        "Сергей": {"role": "devops", "capabilities": ["deployment", "infrastructure"]},
        "Дмитрий": {"role": "ml", "capabilities": ["models", "training"]}
    }
    
    state = await orchestrator.orchestrate(
        user_intent="Оптимизировать производительность системы",
        agents=agents
    )
    
    print("Результат оркестрации:")
    print(f"  Целей: {len(state.goals)}")
    print(f"  Зависимостей: {len(state.dependencies)}")
    print(f"  Прогресс: {state.visualization_data['progress_summary']}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
