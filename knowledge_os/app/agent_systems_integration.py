"""
Agent Systems Integration
Интеграционный модуль для всех систем агентов
Объединяет все новые модули в единую систему
"""

import asyncio
import logging
import os
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Импорты всех систем агентов
try:
    from mentor_system import get_mentor_system
except ImportError:
    get_mentor_system = None

try:
    from prompt_ab_testing import get_prompt_ab_testing
except ImportError:
    get_prompt_ab_testing = None

try:
    from task_prioritizer import get_task_prioritizer
except ImportError:
    get_task_prioritizer = None

try:
    from anomaly_detector import AnomalyDetector
    def get_anomaly_detector():
        return AnomalyDetector()
except ImportError:
    get_anomaly_detector = None

try:
    from early_warning_system import get_early_warning_system
except ImportError:
    get_early_warning_system = None

try:
    from team_formation import get_team_formation_system
except ImportError:
    get_team_formation_system = None

try:
    from agent_kpi_tracker import get_agent_kpi_tracker
except ImportError:
    get_agent_kpi_tracker = None

try:
    from collaboration_forum import get_collaboration_forum
except ImportError:
    get_collaboration_forum = None

try:
    from agent_self_assessment import get_agent_self_assessment
except ImportError:
    get_agent_self_assessment = None

try:
    from checklist_generator import get_checklist_generator
except ImportError:
    get_checklist_generator = None

class AgentSystemsIntegration:
    """
    Интеграция всех систем агентов.
    
    Объединяет все модули в единую систему:
    - Менторство
    - A/B тестирование
    - Приоритизация задач
    - Обнаружение аномалий
    - Раннее предупреждение
    - Командная работа
    - KPI и метрики
    - Коллаборация
    - Самооценка
    - Чеклисты
    """
    
    def __init__(self):
        """Инициализация всех систем агентов"""
        # Инициализируем все системы
        self.mentor_system = get_mentor_system() if get_mentor_system else None
        self.ab_testing = get_prompt_ab_testing() if get_prompt_ab_testing else None
        self.task_prioritizer = get_task_prioritizer() if get_task_prioritizer else None
        self.anomaly_detector = get_anomaly_detector() if get_anomaly_detector else None
        self.early_warning = get_early_warning_system() if get_early_warning_system else None
        self.team_formation = get_team_formation_system() if get_team_formation_system else None
        self.kpi_tracker = get_agent_kpi_tracker() if get_agent_kpi_tracker else None
        self.collab_forum = get_collaboration_forum() if get_collaboration_forum else None
        self.self_assessment = get_agent_self_assessment() if get_agent_self_assessment else None
        self.checklist_gen = get_checklist_generator() if get_checklist_generator else None
        
        logger.info("✅ [AGENT SYSTEMS] Все системы агентов инициализированы")
    
    async def process_agent_activity(
        self,
        agent_id: str,
        activity_type: str,
        activity_data: Dict[str, Any]
    ):
        """
        Обрабатывает активность агента через все системы.
        
        Args:
            agent_id: ID агента
            activity_type: Тип активности ('task_completed', 'signal_generated', etc.)
            activity_data: Данные активности
        """
        try:
            success = activity_data.get('success', True)
            metrics = activity_data.get('metrics', {})
            
            # 1. Обновляем KPI
            if self.kpi_tracker:
                await self.kpi_tracker.get_agent_metrics(agent_id)
            
            # 2. Самооценка после задачи
            if activity_type == 'task_completed' and self.self_assessment:
                task_id = activity_data.get('task_id')
                if task_id:
                    await self.self_assessment.assess_task_performance(
                        agent_id, task_id, activity_data
                    )
            
            # 3. Проверка на аномалии
            if self.anomaly_detector:
                prompt = activity_data.get('prompt', '')
                if prompt:
                    is_injection, _ = self.anomaly_detector.detect_injection(prompt)
                    if is_injection:
                        logger.warning(f"⚠️ [AGENT SYSTEMS] Обнаружена инъекция от агента {agent_id}")
            
            # 4. Проверка ранних предупреждений (раз в час)
            if self.early_warning and datetime.now(timezone.utc).minute == 0:
                warnings = await self.early_warning.check_all_warnings()
                if warnings:
                    for warning in warnings:
                        await self.early_warning.save_warning(warning)
            
            # 5. Обновление рейтинга для менторства
            if self.mentor_system:
                await self.mentor_system.calculate_agent_rating(agent_id)
            
            logger.debug(f"✅ [AGENT SYSTEMS] Активность {activity_type} агента {agent_id} обработана")
            
        except Exception as e:
            logger.error(f"❌ [AGENT SYSTEMS] Ошибка обработки активности: {e}")
    
    async def get_system_status(self) -> Dict[str, Any]:
        """
        Получает статус всех систем агентов.
        
        Returns:
            Словарь со статусом систем
        """
        return {
            'mentor_system': self.mentor_system is not None,
            'ab_testing': self.ab_testing is not None,
            'task_prioritizer': self.task_prioritizer is not None,
            'anomaly_detector': self.anomaly_detector is not None,
            'early_warning': self.early_warning is not None,
            'team_formation': self.team_formation is not None,
            'kpi_tracker': self.kpi_tracker is not None,
            'collab_forum': self.collab_forum is not None,
            'self_assessment': self.self_assessment is not None,
            'checklist_gen': self.checklist_gen is not None
        }

# Singleton instance
_agent_systems_integration_instance: Optional[AgentSystemsIntegration] = None

def get_agent_systems_integration() -> AgentSystemsIntegration:
    """Получить singleton экземпляр AgentSystemsIntegration"""
    global _agent_systems_integration_instance
    if _agent_systems_integration_instance is None:
        _agent_systems_integration_instance = AgentSystemsIntegration()
    return _agent_systems_integration_instance

