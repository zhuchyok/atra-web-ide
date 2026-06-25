"""
[SINGULARITY 26.10] Human-in-the-Loop Approval Mechanism

Мировая практика:
- Human approval для критических действий
- Financial transactions, deployments, public communications
- Очередь approval запросов
"""

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ApprovalType(Enum):
    """Типы действий требующие одобрения"""

    DEPLOYMENT = "deployment"  # Production deployment
    FINANCIAL = "financial"  # Financial transactions
    PUBLIC_COMMUNICATION = "public"  # Public messages/emails
    DATA_DELETE = "data_delete"  # Data deletion
    PERMISSION_CHANGE = "permission"  # Permission changes
    SYSTEM_CHANGE = "system_change"  # System configuration changes
    EXPENSIVE_ACTION = "expensive"  # Actions with high cost


class ApprovalStatus(Enum):
    """Статус заявки на одобрение"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """Заявка на одобрение"""

    id: str
    requester_agent: str  # Кто запрашивает
    approval_type: ApprovalType  # Тип действия
    description: str  # Описание действия
    estimated_impact: str  # Оценка влияния
    trace_id: str  # Trace ID для отслеживания
    requested_at: datetime = field(default_factory=datetime.now)
    status: ApprovalStatus = ApprovalStatus.PENDING
    approver: Optional[str] = None
    approved_at: Optional[datetime] = None
    reason: Optional[str] = None  # Причина отказа/одобрения


class HumanApprovalSystem:
    """
    Система одобрения критических действий человеком.

    Flow:
    1. Агент запрашивает действие через require_approval()
    2. Система создаёт ApprovalRequest
    3. Человек проверяет и одобряет/отклоняет через approve() или reject()
    4. Агент получает результат и продолжает или останавливается
    """

    # Критические действия - требующие одобрения
    APPROVAL_TRIGGERS = {
        "deploy": ApprovalType.DEPLOYMENT,
        "production": ApprovalType.DEPLOYMENT,
        "release": ApprovalType.DEPLOYMENT,
        "payment": ApprovalType.FINANCIAL,
        "transfer": ApprovalType.FINANCIAL,
        "refund": ApprovalType.FINANCIAL,
        "invoice": ApprovalType.FINANCIAL,
        "email": ApprovalType.PUBLIC_COMMUNICATION,
        "public": ApprovalType.PUBLIC_COMMUNICATION,
        "broadcast": ApprovalType.PUBLIC_COMMUNICATION,
        "delete": ApprovalType.DATA_DELETE,
        "drop": ApprovalType.DATA_DELETE,
        "permission": ApprovalType.PERMISSION_CHANGE,
        "access": ApprovalType.PERMISSION_CHANGE,
        "config": ApprovalType.SYSTEM_CHANGE,
        "set_": ApprovalType.SYSTEM_CHANGE,
        "cost>100": ApprovalType.EXPENSIVE_ACTION,
    }

    # TTL для pending запросов (минуты)
    APPROVAL_TTL_MINUTES = 30

    def __init__(self):
        self._approvals: Dict[str, ApprovalRequest] = {}
        self._pending_approvals: List[str] = []
        self._callbacks: Dict[str, asyncio.Future] = {}

    def needs_approval(self, action_description: str) -> Optional[ApprovalType]:
        """Определить нужен ли approval для действия"""
        action_lower = action_description.lower()

        for trigger, approval_type in self.APPROVAL_TRIGGERS.items():
            if trigger in action_lower:
                return approval_type

        return None

    async def request_approval(
        self,
        requester_agent: str,
        action_description: str,
        estimated_impact: str = "",
        trace_id: str = "",
    ) -> str:
        """
        Запросить одобрение действия.
        Returns: approval_request_id
        """
        approval_type = self.needs_approval(action_description)
        if not approval_type:
            return ""  # Не требует одобрения

        approval_id = f"approval_{uuid.uuid4().hex[:12]}"

        request = ApprovalRequest(
            id=approval_id,
            requester_agent=requester_agent,
            approval_type=approval_type,
            description=action_description,
            estimated_impact=estimated_impact,
            trace_id=trace_id,
        )

        self._approvals[approval_id] = request
        self._pending_approvals.append(approval_id)

        # Создаём Future для асинхронного ожидания
        self._callbacks[approval_id] = asyncio.get_event_loop().create_future()

        logger.warning(
            f"[APPROVAL] {approval_type.value.upper()} requested by {requester_agent}: {action_description[:100]}"
        )

        # Запускаем таймер истечения
        asyncio.create_task(self._expire_approval(approval_id))

        return approval_id

    async def _expire_approval(self, approval_id: str):
        """Автоматически истекает необработанные запросы"""
        await asyncio.sleep(self.APPROVAL_TTL_MINUTES * 60)

        if approval_id in self._approvals:
            approval = self._approvals[approval_id]
            if approval.status == ApprovalStatus.PENDING:
                approval.status = ApprovalStatus.EXPIRED
                logger.warning(f"[APPROVAL] {approval_id} EXPIRED")

                if approval_id in self._callbacks:
                    fut = self._callbacks[approval_id]
                    if not fut.done():
                        fut.set_result(False)

    async def approve(self, approval_id: str, approver: str, reason: str = "") -> bool:
        """Одобрить запрос"""
        if approval_id not in self._approvals:
            logger.error(f"[APPROVAL] {approval_id} not found")
            return False

        approval = self._approvals[approval_id]
        approval.status = ApprovalStatus.APPROVED
        approval.approver = approver
        approval.approved_at = datetime.now()
        approval.reason = reason

        if approval_id in self._pending_approvals:
            self._pending_approvals.remove(approval_id)

        if approval_id in self._callbacks:
            fut = self._callbacks[approval_id]
            if not fut.done():
                fut.set_result(True)

        logger.info(f"[APPROVAL] {approval_id} APPROVED by {approver}")
        return True

    async def reject(self, approval_id: str, approver: str, reason: str) -> bool:
        """Отклонить запрос"""
        if approval_id not in self._approvals:
            logger.error(f"[APPROVAL] {approval_id} not found")
            return False

        approval = self._approvals[approval_id]
        approval.status = ApprovalStatus.REJECTED
        approval.approver = approver
        approval.approved_at = datetime.now()
        approval.reason = reason

        if approval_id in self._pending_approvals:
            self._pending_approvals.remove(approval_id)

        if approval_id in self._callbacks:
            fut = self._callbacks[approval_id]
            if not fut.done():
                fut.set_result(False)

        logger.warning(f"[APPROVAL] {approval_id} REJECTED by {approver}: {reason}")
        return True

    async def wait_for_approval(self, approval_id: str, timeout_seconds: int = 1800) -> bool:
        """Ждать решения по approval (max 30 минут по умолчанию)"""
        if approval_id not in self._callbacks:
            return True  # Нет pending - продолжаем

        try:
            result = await asyncio.wait_for(self._callbacks[approval_id], timeout=timeout_seconds)
            return bool(result)
        except asyncio.TimeoutError:
            logger.error(f"[APPROVAL] {approval_id} TIMEOUT")
            return False

    def get_pending(self) -> List[Dict]:
        """Получить все ожидающие запросы"""
        result = []
        for approval_id in self._pending_approvals:
            approval = self._approvals[approval_id]
            result.append(
                {
                    "id": approval.id,
                    "requester": approval.requester_agent,
                    "type": approval.approval_type.value,
                    "description": approval.description[:200],
                    "estimated_impact": approval.estimated_impact,
                    "trace_id": approval.trace_id,
                    "requested_at": approval.requested_at.isoformat(),
                }
            )
        return result

    def get_status(self, approval_id: str) -> Optional[Dict]:
        """Статус конкретного запроса"""
        if approval_id not in self._approvals:
            return None

        approval = self._approvals[approval_id]
        return {
            "id": approval.id,
            "status": approval.status.value,
            "approver": approval.approver,
            "reason": approval.reason,
        }


# Глобальный экземпляр
_approval_system = HumanApprovalSystem()


def get_approval_system() -> HumanApprovalSystem:
    """Получить глобальную систему одобрения"""
    return _approval_system


def requires_approval(action_description: str) -> bool:
    """Декоратор-чекер - требует ли действие одобрения"""
    return _approval_system.needs_approval(action_description) is not None
