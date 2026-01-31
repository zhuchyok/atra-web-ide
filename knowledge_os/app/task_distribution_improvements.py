"""
Task Distribution Improvements - Опциональные улучшения для системы распределения задач
Включает: retry manager, load balancer, validator, escalator, metrics collector
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Импорты с fallback
try:
    from app.task_prioritizer import TaskPriority
except ImportError:
    from enum import Enum
    class TaskPriority(Enum):
        CRITICAL = 1
        HIGH = 2
        MEDIUM = 3
        LOW = 4

try:
    from app.load_balancer import LoadBalancer
    LOAD_BALANCER_AVAILABLE = True
except ImportError:
    LOAD_BALANCER_AVAILABLE = False
    LoadBalancer = None

try:
    from app.metrics_collector import MetricsCollector
    METRICS_COLLECTOR_AVAILABLE = True
except ImportError:
    METRICS_COLLECTOR_AVAILABLE = False
    MetricsCollector = None


class RetryManager:
    """Менеджер повторных попыток для задач"""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Определить, нужно ли повторить попытку"""
        return attempt < self.max_retries

    def get_retry_delay(self, attempt: int) -> float:
        """Получить задержку перед повторной попыткой (exponential backoff)"""
        return min(2.0 ** attempt, 60.0)  # Максимум 60 секунд
    
    async def retry_task_assignment(
        self,
        assignment,
        expert_agent,
        attempt: int = 0
    ):
        """Выполнить задачу с повторными попытками (для совместимости с Task Distribution)"""
        import asyncio
        try:
            result_dict = await expert_agent.run(goal=assignment.subtask, context=None)
            return result_dict
        except Exception as e:
            if self.should_retry(attempt, e):
                delay = self.get_retry_delay(attempt)
                await asyncio.sleep(delay)
                return await self.retry_task_assignment(assignment, expert_agent, attempt + 1)
            else:
                raise


class TaskValidator:
    """Валидатор задач"""

    def validate_task(self, task: dict) -> tuple[bool, Optional[str]]:
        """Валидировать задачу, вернуть (is_valid, error_message)"""
        if not task.get('subtask'):
            return False, "Задача не содержит описания"
        if not task.get('employee_name'):
            return False, "Задача не назначена сотруднику"
        return True, None
    
    async def validate_task_result(
        self,
        assignment,
        original_requirements: str
    ) -> tuple[bool, float, Optional[str]]:
        """Валидировать результат выполнения задачи (для совместимости с Task Distribution)"""
        # Базовая валидация: проверяем, что результат не пустой
        result = assignment.result or ""
        if not result or len(result.strip()) == 0:
            return False, 0.0, "Результат пустой"
        
        # Простая проверка: если результат содержит хотя бы 50 символов, считаем валидным
        if len(result) >= 50:
            # Базовый score: чем длиннее результат, тем выше score (максимум 0.9)
            score = min(0.5 + (len(result) / 1000.0), 0.9)
            return True, score, None
        else:
            return False, 0.3, f"Результат слишком короткий ({len(result)} символов)"


class TaskEscalator:
    """Эскалатор задач для критических ситуаций"""
    
    def should_escalate(self, task: dict, failures: int) -> bool:
        """Определить, нужно ли эскалировать задачу"""
        return failures >= 3 or task.get('priority') == "critical"


# Глобальные экземпляры
_retry_manager: Optional[RetryManager] = None
_load_balancer: Optional[LoadBalancer] = None
_validator: Optional[TaskValidator] = None
_escalator: Optional[TaskEscalator] = None
_metrics_collector: Optional[MetricsCollector] = None


def get_retry_manager() -> RetryManager:
    """Получить менеджер повторных попыток"""
    global _retry_manager
    if _retry_manager is None:
        _retry_manager = RetryManager()
    return _retry_manager


def get_load_balancer() -> Optional[LoadBalancer]:
    """Получить load balancer"""
    global _load_balancer
    if not LOAD_BALANCER_AVAILABLE:
        return None
    if _load_balancer is None:
        try:
            _load_balancer = LoadBalancer()
        except Exception as e:
            logger.debug(f"Не удалось создать LoadBalancer: {e}")
            return None
    return _load_balancer


def get_validator() -> TaskValidator:
    """Получить валидатор задач"""
    global _validator
    if _validator is None:
        _validator = TaskValidator()
    return _validator


def get_escalator() -> TaskEscalator:
    """Получить эскалатор задач"""
    global _escalator
    if _escalator is None:
        _escalator = TaskEscalator()
    return _escalator


def get_metrics_collector() -> Optional[MetricsCollector]:
    """Получить коллектор метрик"""
    global _metrics_collector
    if not METRICS_COLLECTOR_AVAILABLE:
        return None
    if _metrics_collector is None:
        try:
            _metrics_collector = MetricsCollector()
            # Добавляем методы-заглушки для совместимости
            if not hasattr(_metrics_collector, 'record_start'):
                _metrics_collector.record_start = lambda task_id: None
            if not hasattr(_metrics_collector, 'record_assignment'):
                _metrics_collector.record_assignment = lambda task_id, employee_id: None
            if not hasattr(_metrics_collector, 'record_completion'):
                _metrics_collector.record_completion = lambda task_id, success=True: None
            if not hasattr(_metrics_collector, 'get_metrics_summary'):
                _metrics_collector.get_metrics_summary = lambda: {}
        except Exception as e:
            logger.debug(f"Не удалось создать MetricsCollector: {e}")
            return None
    return _metrics_collector
