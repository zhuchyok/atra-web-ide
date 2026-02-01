"""
Multi-Agent Collaboration Framework
Координация между Victoria, Veronica и экспертами
Автоматическая передача задач, делегирование, разрешение конфликтов
"""

import os
import asyncio
import logging
import httpx
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)

# URLs агентов
# В Docker используем host.docker.internal, иначе localhost
is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
if is_docker:
    VICTORIA_URL = os.getenv("VICTORIA_URL", "http://host.docker.internal:8010")
    VERONICA_URL = os.getenv("VERONICA_URL", "http://host.docker.internal:8011")
else:
    VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010")
    VERONICA_URL = os.getenv("VERONICA_URL", "http://localhost:8011")


class TaskType(Enum):
    """Типы задач для делегирования"""
    PLANNING = "planning"  # Victoria специализация
    EXECUTION = "execution"  # Veronica специализация
    REASONING = "reasoning"  # Оба могут
    COMPLEX = "complex"  # Требует координации
    FILE_OPERATION = "file_operation"  # Veronica
    RESEARCH = "research"  # Veronica
    COORDINATION = "coordination"  # Victoria


@dataclass
class Task:
    """Задача для делегирования"""
    task_id: str
    goal: str
    task_type: TaskType
    priority: int = 5  # 1-10, где 10 - высший
    assigned_to: Optional[str] = None
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    dependencies: List[str] = field(default_factory=list)


@dataclass
class CollaborationResult:
    """Результат коллаборации"""
    success: bool
    result: Any
    participants: List[str]
    coordination_steps: List[str]
    total_duration: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class MultiAgentCollaboration:
    """Фреймворк для коллаборации между агентами"""
    
    def __init__(
        self,
        victoria_url: str = VICTORIA_URL,
        veronica_url: str = VERONICA_URL
    ):
        self.victoria_url = victoria_url
        self.veronica_url = veronica_url
        self.tasks: Dict[str, Task] = {}
        self.active_collaborations: Dict[str, List[str]] = {}  # task_id -> [agent_names]
    
    def _classify_task(self, goal: str) -> TaskType:
        """Классифицировать задачу для определения исполнителя"""
        goal_lower = goal.lower()
        
        # Файловые операции - Veronica
        if any(word in goal_lower for word in ["файл", "file", "прочитай", "read", "создай", "create", "удали", "delete"]):
            return TaskType.FILE_OPERATION
        
        # Планирование - Victoria
        if any(word in goal_lower for word in ["спланируй", "plan", "организуй", "organize", "стратегия", "strategy"]):
            return TaskType.PLANNING
        
        # Исследования - Veronica
        if any(word in goal_lower for word in ["найди", "find", "поиск", "search", "исследова", "research"]):
            return TaskType.RESEARCH
        
        # Выполнение - Veronica
        if any(word in goal_lower for word in ["выполни", "execute", "сделай", "do", "запусти", "run"]):
            return TaskType.EXECUTION
        
        # Координация - Victoria
        if any(word in goal_lower for word in ["координируй", "coordinate", "управляй", "manage", "команда", "team"]):
            return TaskType.COORDINATION
        
        # Сложные задачи - требуют координации
        if any(word in goal_lower for word in ["сложн", "complex", "много", "several", "комплекс"]):
            return TaskType.COMPLEX
        
        # По умолчанию - reasoning
        return TaskType.REASONING
    
    async def delegate_task(
        self,
        goal: str,
        preferred_agent: Optional[str] = None,
        priority: int = 5
    ) -> Task:
        """
        Делегировать задачу подходящему агенту
        
        Args:
            goal: Цель задачи
            preferred_agent: Предпочтительный агент (Victoria/Veronica)
            priority: Приоритет задачи (1-10)
        
        Returns:
            Task объект
        """
        task_type = self._classify_task(goal)
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Определяем исполнителя
        if preferred_agent:
            assigned_to = preferred_agent
        elif task_type in [TaskType.PLANNING, TaskType.COORDINATION]:
            assigned_to = "Виктория"
        elif task_type in [TaskType.EXECUTION, TaskType.FILE_OPERATION, TaskType.RESEARCH]:
            assigned_to = "Вероника"
        elif task_type == TaskType.COMPLEX:
            # Сложные задачи требуют координации
            assigned_to = "Виктория"  # Victoria координирует
        else:
            # По умолчанию - Victoria
            assigned_to = "Виктория"
        
        task = Task(
            task_id=task_id,
            goal=goal,
            task_type=task_type,
            priority=priority,
            assigned_to=assigned_to,
            status="pending"
        )
        
        self.tasks[task_id] = task
        logger.info(f"📋 Задача делегирована: {task_id} → {assigned_to} ({task_type.value})")
        
        return task
    
    async def execute_task(self, task: Task) -> CollaborationResult:
        """Выполнить задачу через назначенного агента"""
        start_time = datetime.now(timezone.utc)
        participants = [task.assigned_to]
        coordination_steps = []
        
        try:
            # Определяем URL агента
            if task.assigned_to == "Виктория":
                agent_url = self.victoria_url
            elif task.assigned_to == "Вероника":
                agent_url = self.veronica_url
            else:
                raise ValueError(f"Неизвестный агент: {task.assigned_to}")
            
            coordination_steps.append(f"Задача отправлена {task.assigned_to}")
            
            # Выполняем задачу
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{agent_url}/run",
                    json={"goal": task.goal},
                    timeout=300.0
                )
                response.raise_for_status()
                result_data = response.json()
            
            task.status = "completed"
            task.result = result_data.get("output") or ""
            
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            coordination_steps.append(f"Задача выполнена {task.assigned_to}")
            
            return CollaborationResult(
                success=True,
                result=task.result,
                participants=participants,
                coordination_steps=coordination_steps,
                total_duration=duration,
                metadata={
                    "task_id": task.task_id,
                    "task_type": task.task_type.value,
                    "method": result_data.get("knowledge", {}).get("method", "unknown")
                }
            )
            
        except httpx.HTTPStatusError as e:
            task.status = "failed"
            task.error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            logger.error(f"❌ Ошибка выполнения задачи {task.task_id}: HTTP {e.response.status_code}")
            
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            return CollaborationResult(
                success=False,
                result=None,
                participants=participants,
                coordination_steps=coordination_steps + [f"Ошибка HTTP {e.response.status_code}"],
                total_duration=duration,
                metadata={
                    "task_id": task.task_id,
                    "error": task.error,
                    "agent_url": agent_url
                }
            )
        except httpx.RequestError as e:
            task.status = "failed"
            task.error = f"Connection error: {str(e)}"
            logger.error(f"❌ Ошибка подключения к агенту {task.assigned_to} ({agent_url}): {e}")
            
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            return CollaborationResult(
                success=False,
                result=None,
                participants=participants,
                coordination_steps=coordination_steps + [f"Ошибка подключения: {str(e)}"],
                total_duration=duration,
                metadata={
                    "task_id": task.task_id,
                    "error": task.error,
                    "agent_url": agent_url
                }
            )
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            logger.error(f"❌ Ошибка выполнения задачи {task.task_id}: {e}")
            
            return CollaborationResult(
                success=False,
                result=None,
                participants=participants,
                coordination_steps=coordination_steps + [f"Ошибка: {str(e)}"],
                total_duration=duration,
                metadata={"error": str(e)}
            )
    
    async def coordinate_complex_task(
        self,
        goal: str,
        steps: Optional[List[str]] = None
    ) -> CollaborationResult:
        """
        Координировать выполнение сложной задачи между агентами
        
        Args:
            goal: Главная цель
            steps: Опциональные шаги (если None - Victoria планирует)
        
        Returns:
            CollaborationResult
        """
        start_time = datetime.now(timezone.utc)
        participants = []
        coordination_steps = []
        
        try:
            # Шаг 1: Victoria планирует
            coordination_steps.append("Victoria планирует задачу")
            planning_task = await self.delegate_task(
                f"Спланируй выполнение задачи: {goal}",
                preferred_agent="Виктория",
                priority=10
            )
            planning_result = await self.execute_task(planning_task)
            participants.append("Виктория")
            
            if not planning_result.success:
                raise Exception(f"Ошибка планирования: {planning_result.metadata.get('error')}")
            
            # Извлекаем план из результата
            plan = planning_result.result
            coordination_steps.append(f"План создан: {plan[:100]}...")
            
            # Шаг 2: Veronica выполняет шаги плана
            coordination_steps.append("Veronica выполняет план")
            execution_task = await self.delegate_task(
                f"Выполни план: {plan}\n\nИсходная задача: {goal}",
                preferred_agent="Вероника",
                priority=10
            )
            execution_result = await self.execute_task(execution_task)
            participants.append("Вероника")
            
            if not execution_result.success:
                raise Exception(f"Ошибка выполнения: {execution_result.metadata.get('error')}")
            
            # Шаг 3: Victoria проверяет результат
            coordination_steps.append("Victoria проверяет результат")
            verification_task = await self.delegate_task(
                f"Проверь выполнение задачи: {goal}\n\nРезультат: {execution_result.result}",
                preferred_agent="Виктория",
                priority=8
            )
            verification_result = await self.execute_task(verification_task)
            
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            return CollaborationResult(
                success=True,
                result=execution_result.result,
                participants=list(set(participants + ["Виктория"])),
                coordination_steps=coordination_steps + ["Задача завершена"],
                total_duration=duration,
                metadata={
                    "planning_result": planning_result.result,
                    "execution_result": execution_result.result,
                    "verification_result": verification_result.result
                }
            )
            
        except Exception as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.error(f"❌ Ошибка координации: {e}")
            
            return CollaborationResult(
                success=False,
                result=None,
                participants=participants,
                coordination_steps=coordination_steps + [f"Ошибка: {str(e)}"],
                total_duration=duration,
                metadata={"error": str(e)}
            )
    
    async def resolve_conflict(
        self,
        conflict_description: str,
        agent_opinions: Dict[str, str]
    ) -> str:
        """
        Разрешить конфликт между агентами через консенсус
        
        Args:
            conflict_description: Описание конфликта
            agent_opinions: Мнения агентов {agent_name: opinion}
        
        Returns:
            Решение конфликта
        """
        # Используем Victoria для разрешения конфликта
        agents_list = list(agent_opinions.keys())
        opinions_text = "\n".join([f"{agent}: {opinion}" for agent, opinion in agent_opinions.items()])
        
        resolution_goal = f"""Разреши конфликт:
{conflict_description}

Мнения агентов:
{opinions_text}

Предложи решение, учитывающее все мнения."""
        
        resolution_task = await self.delegate_task(resolution_goal, preferred_agent="Виктория", priority=9)
        resolution_result = await self.execute_task(resolution_task)
        
        if resolution_result.success:
            return resolution_result.result
        else:
            # Fallback - простое большинство
            return max(set(agent_opinions.values()), key=agent_opinions.values().count)
    
    def get_task_status(self, task_id: str) -> Optional[Task]:
        """Получить статус задачи"""
        return self.tasks.get(task_id)
    
    def get_active_tasks(self) -> List[Task]:
        """Получить список активных задач"""
        return [task for task in self.tasks.values() if task.status in ["pending", "in_progress"]]

# Глобальный экземпляр
_collaboration_instance: Optional[MultiAgentCollaboration] = None

def get_collaboration() -> MultiAgentCollaboration:
    """Получить глобальный экземпляр MultiAgentCollaboration"""
    global _collaboration_instance
    if _collaboration_instance is None:
        _collaboration_instance = MultiAgentCollaboration()
    return _collaboration_instance
