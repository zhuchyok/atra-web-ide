"""
Emergent Hierarchy - Динамическое формирование иерархий
Агенты сами определяют структуру и роли на основе задач
"""

import asyncio
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class AgentRole:
    """Роль агента в иерархии"""

    agent_name: str
    role_type: str  # "leader", "coordinator", "specialist", "executor"
    expertise_domains: List[str]
    authority_level: int  # 1-10
    subordinates: List[str] = field(default_factory=list)
    supervisor: Optional[str] = None


@dataclass
class HierarchyNode:
    """Узел иерархии"""

    node_id: str
    agent_name: str
    level: int
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    task_count: int = 0
    success_rate: float = 0.0


class EmergentHierarchy:
    """Система динамического формирования иерархий"""

    def __init__(self):
        self.roles: Dict[str, AgentRole] = {}
        self.hierarchy: Dict[str, HierarchyNode] = {}
        self.task_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.collaboration_matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def _analyze_task_requirements(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Анализировать требования задачи"""
        goal = task.get("goal", "").lower()

        requirements = {
            "complexity": "medium",
            "domains": [],
            "requires_coordination": False,
            "team_size": 1,
        }

        # Определяем домены
        if any(word in goal for word in ["база", "database", "sql", "postgres"]):
            requirements["domains"].append("database")
        if any(word in goal for word in ["api", "сервер", "server", "endpoint"]):
            requirements["domains"].append("backend")
        if any(word in goal for word in ["файл", "file", "код", "code"]):
            requirements["domains"].append("development")
        if any(word in goal for word in ["тест", "test", "проверка"]):
            requirements["domains"].append("testing")

        # Определяем сложность
        if any(word in goal for word in ["сложн", "complex", "много", "several"]):
            requirements["complexity"] = "high"
            requirements["requires_coordination"] = True
            requirements["team_size"] = 3

        return requirements

    async def form_hierarchy_for_task(
        self, task: Dict[str, Any], available_agents: List[str]
    ) -> Dict[str, HierarchyNode]:
        """
        Сформировать иерархию для задачи

        Args:
            task: Задача
            available_agents: Доступные агенты

        Returns:
            Иерархия узлов
        """
        requirements = self._analyze_task_requirements(task)

        # Если простая задача - плоская структура
        if requirements["complexity"] == "low" or requirements["team_size"] == 1:
            node = HierarchyNode(
                node_id=f"node_{available_agents[0]}", agent_name=available_agents[0], level=0
            )
            self.hierarchy[node.node_id] = node
            return {node.node_id: node}

        # Для сложных задач формируем иерархию
        hierarchy = {}

        # Уровень 0: Лидер (Victoria обычно)
        leader = "Виктория" if "Виктория" in available_agents else available_agents[0]
        leader_node = HierarchyNode(node_id=f"node_{leader}", agent_name=leader, level=0)
        hierarchy[leader_node.node_id] = leader_node

        # Уровень 1: Координаторы по доменам
        coordinators = []
        for domain in requirements["domains"]:
            # Находим агента с экспертизой в домене
            coordinator = self._find_domain_expert(domain, available_agents)
            if coordinator and coordinator != leader:
                coord_node = HierarchyNode(
                    node_id=f"node_{coordinator}",
                    agent_name=coordinator,
                    level=1,
                    parent_id=leader_node.node_id,
                )
                hierarchy[coord_node.node_id] = coord_node
                leader_node.children.append(coord_node.node_id)
                coordinators.append(coordinator)

        # Уровень 2: Исполнители
        if requirements["team_size"] > len(coordinators) + 1:
            remaining_agents = [a for a in available_agents if a not in [leader] + coordinators]
            for i, agent in enumerate(
                remaining_agents[: requirements["team_size"] - len(coordinators) - 1]
            ):
                parent = coordinators[i % len(coordinators)] if coordinators else leader
                parent_node_id = f"node_{parent}"

                exec_node = HierarchyNode(
                    node_id=f"node_{agent}", agent_name=agent, level=2, parent_id=parent_node_id
                )
                hierarchy[exec_node.node_id] = exec_node
                if parent_node_id in hierarchy:
                    hierarchy[parent_node_id].children.append(exec_node.node_id)

        # Сохраняем иерархию
        for node in hierarchy.values():
            self.hierarchy[node.node_id] = node

        logger.info(
            f"🏗️ Иерархия сформирована: {len(hierarchy)} узлов, {len([n for n in hierarchy.values() if n.level == 0])} лидеров"
        )

        return hierarchy

    def _find_domain_expert(self, domain: str, available_agents: List[str]) -> Optional[str]:
        """Найти эксперта в домене"""
        # Упрощенная логика - можно улучшить
        domain_mapping = {
            "database": ["Роман", "Игорь"],
            "backend": ["Игорь", "Сергей"],
            "development": ["Игорь", "Вероника"],
            "testing": ["Анна", "Игорь"],
        }

        experts = domain_mapping.get(domain, [])
        for expert in experts:
            if expert in available_agents:
                return expert

        return available_agents[0] if available_agents else None

    async def evolve_hierarchy(self, task_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Эволюционировать иерархию на основе результатов

        Args:
            task_results: Результаты выполнения задач

        Returns:
            Изменения в иерархии
        """
        changes = {"promotions": [], "demotions": [], "new_roles": [], "dissolved_teams": []}

        # Анализируем производительность
        for node_id, node in self.hierarchy.items():
            agent_tasks = self.task_history.get(node.agent_name, [])
            if agent_tasks:
                success_count = sum(1 for t in agent_tasks if t.get("success", False))
                success_rate = success_count / len(agent_tasks) if agent_tasks else 0.0
                node.success_rate = success_rate

                # Продвижение по иерархии при высокой успешности
                if success_rate > 0.9 and node.level > 0:
                    # Можно повысить уровень
                    changes["promotions"].append(
                        {
                            "agent": node.agent_name,
                            "from_level": node.level,
                            "to_level": node.level - 1,
                        }
                    )

                # Понижение при низкой успешности
                if success_rate < 0.5 and node.level < 2:
                    changes["demotions"].append(
                        {
                            "agent": node.agent_name,
                            "from_level": node.level,
                            "to_level": node.level + 1,
                        }
                    )

        logger.info(
            f"🔄 Эволюция иерархии: {len(changes['promotions'])} повышений, {len(changes['demotions'])} понижений"
        )

        return changes

    async def self_organize(
        self, tasks: List[Dict[str, Any]], available_agents: List[str]
    ) -> Dict[str, List[str]]:
        """
        Самоорганизация команды для задач

        Args:
            tasks: Список задач
            available_agents: Доступные агенты

        Returns:
            Распределение задач по агентам
        """
        assignment = defaultdict(list)

        for task in tasks:
            requirements = self._analyze_task_requirements(task)

            # Формируем команду
            if requirements["requires_coordination"]:
                hierarchy = await self.form_hierarchy_for_task(task, available_agents)
                # Назначаем задачу лидеру
                leader_nodes = [n for n in hierarchy.values() if n.level == 0]
                if leader_nodes:
                    assignment[leader_nodes[0].agent_name].append(task.get("goal", ""))
            else:
                # Простая задача - назначаем подходящему агенту
                agent = self._find_best_agent_for_task(task, available_agents)
                if agent:
                    assignment[agent].append(task.get("goal", ""))

        return dict(assignment)

    def _find_best_agent_for_task(
        self, task: Dict[str, Any], available_agents: List[str]
    ) -> Optional[str]:
        """Найти лучшего агента для задачи"""
        requirements = self._analyze_task_requirements(task)

        # Упрощенная логика выбора
        if requirements["domains"]:
            expert = self._find_domain_expert(requirements["domains"][0], available_agents)
            if expert:
                return expert

        return available_agents[0] if available_agents else None

    def record_task_result(
        self,
        agent_name: str,
        task: Dict[str, Any],
        success: bool,
        performance_metrics: Dict[str, Any] = None,
    ):
        """Записать результат задачи для анализа"""
        self.task_history[agent_name].append(
            {
                "task": task,
                "success": success,
                "metrics": performance_metrics or {},
                "timestamp": datetime.now(timezone.utc),
            }
        )

    def get_hierarchy_statistics(self) -> Dict[str, Any]:
        """Получить статистику иерархии"""
        return {
            "total_nodes": len(self.hierarchy),
            "levels": len(set(n.level for n in self.hierarchy.values())),
            "leaders": len([n for n in self.hierarchy.values() if n.level == 0]),
            "coordinators": len([n for n in self.hierarchy.values() if n.level == 1]),
            "executors": len([n for n in self.hierarchy.values() if n.level == 2]),
            "average_success_rate": sum(n.success_rate for n in self.hierarchy.values())
            / len(self.hierarchy)
            if self.hierarchy
            else 0.0,
        }


# Глобальный экземпляр
_emergent_hierarchy: Optional[EmergentHierarchy] = None


def get_emergent_hierarchy() -> EmergentHierarchy:
    """Получить глобальный экземпляр EmergentHierarchy"""
    global _emergent_hierarchy
    if _emergent_hierarchy is None:
        _emergent_hierarchy = EmergentHierarchy()
    return _emergent_hierarchy
