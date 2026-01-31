"""
Task Prioritizer
Система приоритизации задач для автоматического распределения работы между агентами
AGENT IMPROVEMENTS: Система приоритизации задач
"""

import asyncio
import logging
import os
import json
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)

# Database connection
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

class TaskPriority(Enum):
    """Приоритет задачи"""
    CRITICAL = 1  # Критичная (блокирует работу)
    HIGH = 2      # Высокая (важное влияние)
    MEDIUM = 3    # Средняя
    LOW = 4       # Низкая

class TaskStatus(Enum):
    """Статус задачи"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Task:
    """Задача для выполнения"""
    task_id: str
    task_type: str  # 'code_review', 'bug_fix', 'feature', 'optimization', etc.
    description: str
    priority: TaskPriority
    complexity: float  # 0.0-1.0 (оценка сложности)
    impact: float  # 0.0-1.0 (влияние на метрики)
    dependencies: List[str]  # ID зависимых задач
    assigned_agent: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = None
    estimated_time: Optional[float] = None  # Оценка времени в часах
    metadata: Dict[str, Any] = None

class TaskPrioritizer:
    """
    Система приоритизации задач.
    
    Функционал:
    - Автоматическая оценка важности задач (критичность, влияние, сложность)
    - Распределение задач между агентами по приоритету
    - Балансировка нагрузки между агентами
    - Оптимизация очереди задач
    - Мониторинг времени выполнения задач
    """
    
    def __init__(self, db_url: str = DB_URL):
        """
        Args:
            db_url: URL базы данных
        """
        self.db_url = db_url
        self._task_queue: List[Task] = []
        self._agent_loads: Dict[str, int] = defaultdict(int)  # agent_id -> количество задач
        self._task_cache: Dict[str, Task] = {}
        
    async def _get_conn(self):
        """Получить подключение к БД"""
        if not ASYNCPG_AVAILABLE:
            logger.error("asyncpg is not installed. Database connection unavailable.")
            return None
        try:
            conn = await asyncpg.connect(self.db_url)
            return conn
        except Exception as e:
            logger.error(f"❌ [TASK PRIORITIZER] Ошибка подключения к БД: {e}")
            return None
    
    def calculate_priority_score(
        self,
        criticality: float,
        impact: float,
        complexity: float,
        dependencies_count: int
    ) -> Tuple[TaskPriority, float]:
        """
        Рассчитывает приоритет задачи на основе критериев.
        
        Args:
            criticality: Критичность (0.0-1.0) - блокирует ли работу
            impact: Влияние на метрики (0.0-1.0)
            complexity: Сложность (0.0-1.0) - чем выше, тем сложнее
            dependencies_count: Количество зависимостей
        
        Returns:
            Tuple[TaskPriority, score] где score - числовой приоритет (меньше = выше приоритет)
        """
        # Веса для критериев
        criticality_weight = 0.4
        impact_weight = 0.3
        complexity_weight = -0.2  # Отрицательный - простые задачи приоритетнее
        dependencies_weight = -0.1  # Отрицательный - задачи без зависимостей приоритетнее
        
        # Нормализуем dependencies_count (0-10 -> 0-1)
        normalized_deps = min(dependencies_count / 10.0, 1.0)
        
        # Рассчитываем score (меньше = выше приоритет)
        score = (
            criticality * criticality_weight +
            impact * impact_weight +
            complexity * complexity_weight +
            normalized_deps * dependencies_weight
        )
        
        # Инвертируем score для приоритета (высокий score = высокий приоритет)
        priority_score = 1.0 - score
        
        # Определяем приоритет
        if criticality >= 0.8 or (impact >= 0.8 and criticality >= 0.5):
            priority = TaskPriority.CRITICAL
        elif priority_score >= 0.6:
            priority = TaskPriority.HIGH
        elif priority_score >= 0.4:
            priority = TaskPriority.MEDIUM
        else:
            priority = TaskPriority.LOW
        
        return priority, priority_score
    
    async def add_task(
        self,
        task_type: str,
        description: str,
        criticality: float = 0.5,
        impact: float = 0.5,
        complexity: float = 0.5,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Добавляет задачу в очередь с автоматическим расчетом приоритета.
        
        Args:
            task_type: Тип задачи
            description: Описание задачи
            criticality: Критичность (0.0-1.0)
            impact: Влияние (0.0-1.0)
            complexity: Сложность (0.0-1.0)
            dependencies: Список ID зависимых задач
            metadata: Дополнительные метаданные
        
        Returns:
            task_id
        """
        try:
            # Генерируем task_id
            import hashlib
            task_key = f"{task_type}:{description}:{datetime.now(timezone.utc).isoformat()}"
            task_id = hashlib.md5(task_key.encode()).hexdigest()[:16]
            
            # Рассчитываем приоритет
            priority, priority_score = self.calculate_priority_score(
                criticality, impact, complexity, len(dependencies or [])
            )
            
            # Создаем задачу
            task = Task(
                task_id=task_id,
                task_type=task_type,
                description=description,
                priority=priority,
                complexity=complexity,
                impact=impact,
                dependencies=dependencies or [],
                status=TaskStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                metadata=metadata or {}
            )
            
            # Добавляем в очередь (сортировка по приоритету)
            self._task_queue.append(task)
            self._task_queue.sort(key=lambda t: (t.priority.value, -priority_score))
            
            # Сохраняем в БД
            conn = await self._get_conn()
            if conn:
                try:
                    # Проверяем наличие таблицы tasks
                    table_exists = await conn.fetchval("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_name = 'agent_tasks'
                        )
                    """)
                    
                    if table_exists:
                        await conn.execute("""
                            INSERT INTO agent_tasks (task_id, task_type, description, priority, complexity, impact, dependencies, status, created_at, metadata)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                            ON CONFLICT (task_id) DO UPDATE
                            SET priority = EXCLUDED.priority, status = EXCLUDED.status
                        """, task_id, task_type, description, priority.value, complexity, impact, json.dumps(dependencies or []), task.status.value, task.created_at, json.dumps(metadata or {}))
                    
                    # Обновляем кэш
                    self._task_cache[task_id] = task
                    
                    logger.info(f"✅ [TASK PRIORITIZER] Добавлена задача {task_id} с приоритетом {priority.name}")
                    return task_id
                    
                finally:
                    await conn.close()
            
            return task_id
            
        except Exception as e:
            logger.error(f"❌ [TASK PRIORITIZER] Ошибка добавления задачи: {e}")
            return ""
    
    async def assign_task(self, task_id: str, agent_id: str) -> bool:
        """
        Назначает задачу агенту.
        
        Args:
            task_id: ID задачи
            agent_id: ID агента
        
        Returns:
            True если назначение успешно
        """
        try:
            # Находим задачу
            task = self._task_cache.get(task_id)
            if not task:
                # Пробуем загрузить из БД
                conn = await self._get_conn()
                if conn:
                    try:
                        row = await conn.fetchrow("""
                            SELECT task_id, task_type, description, priority, complexity, impact, dependencies, status, assigned_agent
                            FROM agent_tasks
                            WHERE task_id = $1
                        """, task_id)
                        if row:
                            task = Task(
                                task_id=row['task_id'],
                                task_type=row['task_type'],
                                description=row['description'],
                                priority=TaskPriority(row['priority']),
                                complexity=float(row['complexity']),
                                impact=float(row['impact']),
                                dependencies=json.loads(row['dependencies']) if isinstance(row['dependencies'], str) else row['dependencies'],
                                status=TaskStatus(row['status']),
                                assigned_agent=row['assigned_agent']
                            )
                            self._task_cache[task_id] = task
                    finally:
                        await conn.close()
            
            if not task:
                logger.warning(f"⚠️ [TASK PRIORITIZER] Задача {task_id} не найдена")
                return False
            
            # Проверяем, что задача не назначена другому агенту
            if task.assigned_agent and task.assigned_agent != agent_id:
                logger.warning(f"⚠️ [TASK PRIORITIZER] Задача {task_id} уже назначена агенту {task.assigned_agent}")
                return False
            
            # Назначаем задачу
            task.assigned_agent = agent_id
            task.status = TaskStatus.IN_PROGRESS
            
            # Обновляем нагрузку агента
            self._agent_loads[agent_id] += 1
            
            # Обновляем в БД
            conn = await self._get_conn()
            if conn:
                try:
                    table_exists = await conn.fetchval("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_name = 'agent_tasks'
                        )
                    """)
                    
                    if table_exists:
                        await conn.execute("""
                            UPDATE agent_tasks
                            SET assigned_agent = $1, status = $2
                            WHERE task_id = $3
                        """, agent_id, task.status.value, task_id)
                    
                    logger.info(f"✅ [TASK PRIORITIZER] Задача {task_id} назначена агенту {agent_id}")
                    return True
                    
                finally:
                    await conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [TASK PRIORITIZER] Ошибка назначения задачи: {e}")
            return False
    
    async def get_next_task(self, agent_id: Optional[str] = None) -> Optional[Task]:
        """
        Получает следующую задачу из очереди (с учетом балансировки нагрузки).
        
        Args:
            agent_id: ID агента (если указан, учитывается его текущая нагрузка)
        
        Returns:
            Task или None
        """
        try:
            # Фильтруем задачи по статусу (только PENDING)
            pending_tasks = [t for t in self._task_queue if t.status == TaskStatus.PENDING]
            
            if not pending_tasks:
                # Пробуем загрузить из БД
                conn = await self._get_conn()
                if conn:
                    try:
                        rows = await conn.fetch("""
                            SELECT task_id, task_type, description, priority, complexity, impact, dependencies, status, metadata
                            FROM agent_tasks
                            WHERE status = 'pending'
                            ORDER BY priority ASC, created_at ASC
                            LIMIT 10
                        """)
                        for row in rows:
                            task = Task(
                                task_id=row['task_id'],
                                task_type=row['task_type'],
                                description=row['description'],
                                priority=TaskPriority(row['priority']),
                                complexity=float(row['complexity']),
                                impact=float(row['impact']),
                                dependencies=json.loads(row['dependencies']) if isinstance(row['dependencies'], str) else row['dependencies'],
                                status=TaskStatus(row['status']),
                                metadata=json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
                            )
                            if task not in self._task_queue:
                                self._task_queue.append(task)
                                self._task_cache[task.task_id] = task
                    finally:
                        await conn.close()
                
                pending_tasks = [t for t in self._task_queue if t.status == TaskStatus.PENDING]
            
            if not pending_tasks:
                return None
            
            # Если указан agent_id, учитываем его нагрузку
            if agent_id:
                agent_load = self._agent_loads.get(agent_id, 0)
                # Если у агента слишком много задач, не даем новую
                if agent_load >= 5:  # Максимум 5 задач на агента
                    logger.debug(f"⚠️ [TASK PRIORITIZER] Агент {agent_id} перегружен ({agent_load} задач)")
                    return None
            
            # Выбираем задачу с наивысшим приоритетом
            next_task = pending_tasks[0]
            return next_task
            
        except Exception as e:
            logger.error(f"❌ [TASK PRIORITIZER] Ошибка получения следующей задачи: {e}")
            return None
    
    async def complete_task(self, task_id: str, success: bool = True) -> bool:
        """
        Отмечает задачу как выполненную.
        
        Args:
            task_id: ID задачи
            success: Успешно ли выполнена
        
        Returns:
            True если обновление успешно
        """
        try:
            task = self._task_cache.get(task_id)
            if not task:
                return False
            
            # Обновляем статус
            task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
            
            # Уменьшаем нагрузку агента
            if task.assigned_agent:
                self._agent_loads[task.assigned_agent] = max(0, self._agent_loads.get(task.assigned_agent, 0) - 1)
            
            # Обновляем в БД
            conn = await self._get_conn()
            if conn:
                try:
                    table_exists = await conn.fetchval("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_name = 'agent_tasks'
                        )
                    """)
                    
                    if table_exists:
                        await conn.execute("""
                            UPDATE agent_tasks
                            SET status = $1, completed_at = $2
                            WHERE task_id = $3
                        """, task.status.value, datetime.now(timezone.utc), task_id)
                    
                    logger.info(f"✅ [TASK PRIORITIZER] Задача {task_id} отмечена как {task.status.value}")
                    return True
                    
                finally:
                    await conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [TASK PRIORITIZER] Ошибка завершения задачи: {e}")
            return False
    
    async def get_agent_load(self, agent_id: str) -> int:
        """
        Получает текущую нагрузку агента.
        
        Args:
            agent_id: ID агента
        
        Returns:
            Количество активных задач
        """
        return self._agent_loads.get(agent_id, 0)
    
    async def get_queue_statistics(self) -> Dict[str, Any]:
        """
        Получает статистику очереди задач.
        
        Returns:
            Словарь со статистикой
        """
        try:
            pending = len([t for t in self._task_queue if t.status == TaskStatus.PENDING])
            in_progress = len([t for t in self._task_queue if t.status == TaskStatus.IN_PROGRESS])
            completed = len([t for t in self._task_queue if t.status == TaskStatus.COMPLETED])
            failed = len([t for t in self._task_queue if t.status == TaskStatus.FAILED])
            
            # Распределение по приоритетам
            priority_dist = defaultdict(int)
            for task in self._task_queue:
                priority_dist[task.priority.name] += 1
            
            return {
                'total_tasks': len(self._task_queue),
                'pending': pending,
                'in_progress': in_progress,
                'completed': completed,
                'failed': failed,
                'priority_distribution': dict(priority_dist),
                'agent_loads': dict(self._agent_loads)
            }
            
        except Exception as e:
            logger.error(f"❌ [TASK PRIORITIZER] Ошибка получения статистики: {e}")
            return {}

# Singleton instance
_task_prioritizer_instance: Optional[TaskPrioritizer] = None

def get_task_prioritizer(db_url: str = DB_URL) -> TaskPrioritizer:
    """Получить singleton экземпляр TaskPrioritizer"""
    global _task_prioritizer_instance
    if _task_prioritizer_instance is None:
        _task_prioritizer_instance = TaskPrioritizer(db_url=db_url)
    return _task_prioritizer_instance

