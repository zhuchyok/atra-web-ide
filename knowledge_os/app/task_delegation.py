"""
Task Delegation - Умное распределение задач между агентами
Анализ задачи и автоматический выбор оптимального исполнителя
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from app.multi_agent_collaboration import TaskType, Task, MultiAgentCollaboration

logger = logging.getLogger(__name__)


class AgentCapability(Enum):
    """Способности агентов"""
    PLANNING = "planning"
    EXECUTION = "execution"
    REASONING = "reasoning"
    FILE_OPERATIONS = "file_operations"
    RESEARCH = "research"
    COORDINATION = "coordination"
    CODE_ANALYSIS = "code_analysis"
    SYSTEM_ADMIN = "system_admin"


@dataclass
class AgentProfile:
    """Профиль агента с его способностями"""
    name: str
    capabilities: List[AgentCapability]
    efficiency_scores: Dict[AgentCapability, float]  # 0.0-1.0
    current_load: int = 0
    max_concurrent_tasks: int = 5


class TaskDelegator:
    """Умный делегатор задач"""
    
    def __init__(self):
        self.collaboration = MultiAgentCollaboration()
        
        # Профили агентов
        self.agent_profiles = {
            "Victoria": AgentProfile(
                name="Victoria",
                capabilities=[
                    AgentCapability.PLANNING,
                    AgentCapability.REASONING,
                    AgentCapability.COORDINATION,
                    AgentCapability.CODE_ANALYSIS
                ],
                efficiency_scores={
                    AgentCapability.PLANNING: 0.95,
                    AgentCapability.REASONING: 0.90,
                    AgentCapability.COORDINATION: 0.98,
                    AgentCapability.CODE_ANALYSIS: 0.85
                },
                max_concurrent_tasks=10
            ),
            "Veronica": AgentProfile(
                name="Veronica",
                capabilities=[
                    AgentCapability.EXECUTION,
                    AgentCapability.FILE_OPERATIONS,
                    AgentCapability.RESEARCH,
                    AgentCapability.SYSTEM_ADMIN
                ],
                efficiency_scores={
                    AgentCapability.EXECUTION: 0.95,
                    AgentCapability.FILE_OPERATIONS: 0.98,
                    AgentCapability.RESEARCH: 0.90,
                    AgentCapability.SYSTEM_ADMIN: 0.85
                },
                max_concurrent_tasks=8
            )
        }
    
    def analyze_task(self, goal: str) -> Dict[str, Any]:
        """
        Анализировать задачу для определения требований
        
        Returns:
            Словарь с требованиями задачи
        """
        goal_lower = goal.lower()
        
        requirements = {
            "complexity": "medium",  # simple, medium, complex
            "required_capabilities": [],
            "estimated_duration": "medium",  # short, medium, long
            "requires_coordination": False,
            "priority_hint": 5
        }
        
        # Определяем сложность
        complex_indicators = ["сложн", "complex", "много", "several", "комплекс", "интеграция"]
        if any(indicator in goal_lower for indicator in complex_indicators):
            requirements["complexity"] = "complex"
            requirements["requires_coordination"] = True
        
        # Определяем требуемые способности
        if any(word in goal_lower for word in ["спланируй", "plan", "организуй", "organize"]):
            requirements["required_capabilities"].append(AgentCapability.PLANNING)
        
        if any(word in goal_lower for word in ["выполни", "execute", "сделай", "do"]):
            requirements["required_capabilities"].append(AgentCapability.EXECUTION)
        
        if any(word in goal_lower for word in ["файл", "file", "прочитай", "read"]):
            requirements["required_capabilities"].append(AgentCapability.FILE_OPERATIONS)
        
        if any(word in goal_lower for word in ["найди", "find", "поиск", "search"]):
            requirements["required_capabilities"].append(AgentCapability.RESEARCH)
        
        # Определяем приоритет
        if any(word in goal_lower for word in ["срочно", "urgent", "критично", "critical"]):
            requirements["priority_hint"] = 9
        elif any(word in goal_lower for word in ["важно", "important"]):
            requirements["priority_hint"] = 7
        
        return requirements
    
    def select_best_agent(
        self,
        task_requirements: Dict[str, Any],
        preferred_agent: Optional[str] = None
    ) -> str:
        """
        Выбрать лучшего агента для задачи
        
        Args:
            task_requirements: Требования задачи
            preferred_agent: Предпочтительный агент
        
        Returns:
            Имя выбранного агента
        """
        if preferred_agent and preferred_agent in self.agent_profiles:
            return preferred_agent
        
        required_capabilities = task_requirements.get("required_capabilities", [])
        
        if not required_capabilities:
            # Если нет специфических требований, используем классификацию задачи
            task_type = self.collaboration._classify_task(task_requirements.get("goal", ""))
            if task_type in [TaskType.PLANNING, TaskType.COORDINATION]:
                return "Victoria"
            else:
                return "Veronica"
        
        # Оцениваем агентов по требуемым способностям
        agent_scores = {}
        
        for agent_name, profile in self.agent_profiles.items():
            score = 0.0
            matching_capabilities = 0
            
            for capability in required_capabilities:
                if capability in profile.capabilities:
                    score += profile.efficiency_scores.get(capability, 0.5)
                    matching_capabilities += 1
            
            # Учитываем загрузку агента
            load_factor = 1.0 - (profile.current_load / profile.max_concurrent_tasks) * 0.3
            
            if matching_capabilities > 0:
                agent_scores[agent_name] = (score / matching_capabilities) * load_factor
            else:
                agent_scores[agent_name] = 0.0
        
        # Выбираем агента с наивысшим score
        if agent_scores:
            best_agent = max(agent_scores.items(), key=lambda x: x[1])[0]
            logger.info(f"🎯 Выбран агент: {best_agent} (score: {agent_scores[best_agent]:.2f})")
            return best_agent
        
        # Fallback
        return "Victoria"
    
    async def delegate_smart(
        self,
        goal: str,
        preferred_agent: Optional[str] = None,
        priority: Optional[int] = None
    ) -> Task:
        """
        Умное делегирование задачи
        
        Args:
            goal: Цель задачи
            preferred_agent: Предпочтительный агент
            priority: Приоритет (если None - определяется автоматически)
        
        Returns:
            Task объект
        """
        # Анализируем задачу
        requirements = self.analyze_task(goal)
        requirements["goal"] = goal
        
        # Определяем приоритет
        if priority is None:
            priority = requirements.get("priority_hint", 5)
        
        # Выбираем лучшего агента
        best_agent = self.select_best_agent(requirements, preferred_agent)
        
        # Делегируем задачу
        task = await self.collaboration.delegate_task(
            goal=goal,
            preferred_agent=best_agent,
            priority=priority
        )
        
        logger.info(f"📋 Умное делегирование: {task.task_id} → {best_agent} (приоритет: {priority})")
        
        return task
    
    def update_agent_load(self, agent_name: str, load: int):
        """Обновить загрузку агента"""
        if agent_name in self.agent_profiles:
            self.agent_profiles[agent_name].current_load = load

# Глобальный экземпляр
_task_delegator: Optional[TaskDelegator] = None

def get_task_delegator() -> TaskDelegator:
    """Получить глобальный экземпляр TaskDelegator"""
    global _task_delegator
    if _task_delegator is None:
        _task_delegator = TaskDelegator()
    return _task_delegator
