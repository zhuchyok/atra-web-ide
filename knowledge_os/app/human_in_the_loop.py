"""
Human-in-the-Loop (HITL) Framework
Критические одобрения, интерактивная коррекция, feedback loops
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json

logger = logging.getLogger(__name__)

# Попытка использовать БД для хранения одобрений
try:
    import asyncpg
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.debug("ℹ️ asyncpg не доступен, одобрения будут храниться в памяти (опциональный компонент)")


class ApprovalStatus(Enum):
    """Статус одобрения"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class ActionCriticality(Enum):
    """Критичность действия"""
    LOW = "low"  # Автоматическое выполнение
    MEDIUM = "medium"  # Уведомление
    HIGH = "high"  # Требует одобрения
    CRITICAL = "critical"  # Обязательное одобрение


@dataclass
class ApprovalRequest:
    """Запрос на одобрение"""
    request_id: str
    action: str
    description: str
    criticality: ActionCriticality
    agent_name: str
    proposed_result: Any
    context: Dict[str, Any] = field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    feedback: Optional[str] = None
    modified_result: Optional[Any] = None


@dataclass
class FeedbackEntry:
    """Запись обратной связи"""
    feedback_id: str
    action_id: str
    agent_name: str
    feedback_type: str  # "correction", "improvement", "approval"
    feedback_text: str
    rating: Optional[int] = None  # 1-5
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class HumanInTheLoop:
    """Фреймворк Human-in-the-Loop"""
    
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.getenv("DATABASE_URL")
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        self.feedback_history: List[FeedbackEntry] = []
        self.approval_callbacks: Dict[str, Callable] = {}
        self.confidence_threshold = float(os.getenv("HITL_CONFIDENCE_THRESHOLD", "0.7"))
        
        # Критические действия, требующие одобрения
        self.critical_actions = {
            "delete": ActionCriticality.CRITICAL,
            "drop": ActionCriticality.CRITICAL,
            "remove": ActionCriticality.CRITICAL,
            "uninstall": ActionCriticality.CRITICAL,
            "destroy": ActionCriticality.CRITICAL,
            "modify_system": ActionCriticality.HIGH,
            "install": ActionCriticality.HIGH,
            "update_config": ActionCriticality.MEDIUM,
            "create": ActionCriticality.LOW,
            "read": ActionCriticality.LOW,
            "plan_approval": ActionCriticality.HIGH,
            "complex_task": ActionCriticality.HIGH,
        }
    
    def _assess_criticality(self, action: str, context: Dict[str, Any]) -> ActionCriticality:
        """Оценить критичность действия"""
        action_lower = action.lower()
        
        # Проверяем ключевые слова
        for keyword, criticality in self.critical_actions.items():
            if keyword in action_lower:
                return criticality
        
        # Проверяем контекст
        if context.get("system_file", False):
            return ActionCriticality.HIGH
        
        if context.get("production", False):
            return ActionCriticality.HIGH
        
        # Проверяем confidence
        confidence = context.get("confidence", 1.0)
        if confidence < self.confidence_threshold:
            return ActionCriticality.MEDIUM
        
        return ActionCriticality.LOW
    
    async def request_approval(
        self,
        action: str,
        description: str,
        agent_name: str,
        proposed_result: Any,
        context: Dict[str, Any] = None
    ) -> ApprovalRequest:
        """
        Запросить одобрение действия
        
        Args:
            action: Действие для одобрения
            description: Описание действия
            agent_name: Имя агента
            proposed_result: Предлагаемый результат
            context: Дополнительный контекст
        
        Returns:
            ApprovalRequest
        """
        context = context or {}
        criticality = self._assess_criticality(action, context)
        
        request_id = f"approval_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        approval_request = ApprovalRequest(
            request_id=request_id,
            action=action,
            description=description,
            criticality=criticality,
            agent_name=agent_name,
            proposed_result=proposed_result,
            context=context
        )
        
        self.pending_approvals[request_id] = approval_request
        
        # Если критичность высокая - требуем одобрения
        if criticality in [ActionCriticality.HIGH, ActionCriticality.CRITICAL]:
            logger.warning(f"⚠️ Требуется одобрение: {action} (критичность: {criticality.value})")
            # Здесь можно добавить уведомление пользователю (Telegram, email и т.д.)
        
        return approval_request
    
    async def approve(
        self,
        request_id: str,
        approved_by: str = "human",
        feedback: Optional[str] = None,
        modified_result: Optional[Any] = None
    ) -> bool:
        """
        Одобрить действие
        
        Args:
            request_id: ID запроса
            approved_by: Кто одобрил
            feedback: Обратная связь
            modified_result: Модифицированный результат (если был изменен)
        
        Returns:
            True если одобрено
        """
        if request_id not in self.pending_approvals:
            logger.error(f"❌ Запрос на одобрение не найден: {request_id}")
            return False
        
        approval = self.pending_approvals[request_id]
        approval.status = ApprovalStatus.APPROVED
        approval.approved_at = datetime.now(timezone.utc)
        approval.approved_by = approved_by
        approval.feedback = feedback
        
        if modified_result is not None:
            approval.status = ApprovalStatus.MODIFIED
            approval.modified_result = modified_result
        
        logger.info(f"✅ Действие одобрено: {approval.action} ({approved_by})")
        
        # Вызываем callback если есть
        if request_id in self.approval_callbacks:
            callback = self.approval_callbacks[request_id]
            result = modified_result if modified_result is not None else approval.proposed_result
            await callback(result)
            del self.approval_callbacks[request_id]
        
        return True
    
    async def reject(
        self,
        request_id: str,
        rejected_by: str = "human",
        reason: Optional[str] = None
    ) -> bool:
        """
        Отклонить действие
        
        Args:
            request_id: ID запроса
            rejected_by: Кто отклонил
            reason: Причина отклонения
        
        Returns:
            True если отклонено
        """
        if request_id not in self.pending_approvals:
            logger.error(f"❌ Запрос на одобрение не найден: {request_id}")
            return False
        
        approval = self.pending_approvals[request_id]
        approval.status = ApprovalStatus.REJECTED
        approval.approved_at = datetime.now(timezone.utc)
        approval.approved_by = rejected_by
        approval.feedback = reason or "Отклонено пользователем"
        
        logger.warning(f"❌ Действие отклонено: {approval.action} ({rejected_by})")
        
        return True
    
    async def check_approval_required(
        self,
        action: str,
        context: Dict[str, Any] = None
    ) -> bool:
        """
        Проверить, требуется ли одобрение для действия
        
        Args:
            action: Действие
            context: Контекст
        
        Returns:
            True если требуется одобрение
        """
        context = context or {}
        criticality = self._assess_criticality(action, context)
        return criticality in [ActionCriticality.HIGH, ActionCriticality.CRITICAL]
    
    async def record_feedback(
        self,
        action_id: str,
        agent_name: str,
        feedback_type: str,
        feedback_text: str,
        rating: Optional[int] = None
    ) -> FeedbackEntry:
        """
        Записать обратную связь
        
        Args:
            action_id: ID действия
            agent_name: Имя агента
            feedback_type: Тип фидбека
            feedback_text: Текст фидбека
            rating: Рейтинг (1-5)
        
        Returns:
            FeedbackEntry
        """
        feedback_id = f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        feedback = FeedbackEntry(
            feedback_id=feedback_id,
            action_id=action_id,
            agent_name=agent_name,
            feedback_type=feedback_type,
            feedback_text=feedback_text,
            rating=rating
        )
        
        self.feedback_history.append(feedback)
        logger.info(f"📝 Обратная связь записана: {agent_name} - {feedback_type}")
        
        return feedback
    
    async def get_pending_approvals(self) -> List[ApprovalRequest]:
        """Получить список ожидающих одобрения"""
        return [
            approval for approval in self.pending_approvals.values()
            if approval.status == ApprovalStatus.PENDING
        ]
    
    async def learn_from_feedback(self, agent_name: str) -> Dict[str, Any]:
        """
        Обучение на основе обратной связи
        
        Args:
            agent_name: Имя агента
        
        Returns:
            Статистика и рекомендации
        """
        agent_feedback = [
            f for f in self.feedback_history
            if f.agent_name == agent_name
        ]
        
        if not agent_feedback:
            return {"message": "Нет обратной связи для обучения"}
        
        # Анализ фидбека
        total = len(agent_feedback)
        corrections = sum(1 for f in agent_feedback if f.feedback_type == "correction")
        improvements = sum(1 for f in agent_feedback if f.feedback_type == "improvement")
        avg_rating = sum(f.rating for f in agent_feedback if f.rating) / total if any(f.rating for f in agent_feedback) else None
        
        return {
            "total_feedback": total,
            "corrections": corrections,
            "improvements": improvements,
            "average_rating": avg_rating,
            "correction_rate": corrections / total if total > 0 else 0,
            "recommendations": self._generate_recommendations(agent_feedback)
        }
    
    def _generate_recommendations(self, feedback: List[FeedbackEntry]) -> List[str]:
        """Генерация рекомендаций на основе фидбека"""
        recommendations = []
        
        # Анализируем частые ошибки
        corrections = [f for f in feedback if f.feedback_type == "correction"]
        if len(corrections) > len(feedback) * 0.3:
            recommendations.append("Высокий процент исправлений - требуется улучшение точности")
        
        # Анализируем рейтинги
        ratings = [f.rating for f in feedback if f.rating]
        if ratings and sum(ratings) / len(ratings) < 3:
            recommendations.append("Низкий средний рейтинг - требуется улучшение качества")
        
        return recommendations

# Глобальный экземпляр
_hitl_instance: Optional[HumanInTheLoop] = None

def get_hitl() -> HumanInTheLoop:
    """Получить глобальный экземпляр HumanInTheLoop"""
    global _hitl_instance
    if _hitl_instance is None:
        _hitl_instance = HumanInTheLoop()
    return _hitl_instance
