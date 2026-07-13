"""
Explicit Handoffs - Явные и структурированные handoffs между агентами
На основе практики Meta: Explicit handoffs с schemas и validators
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HandoffStatus(Enum):
    """Статус handoff"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HandoffPriority(Enum):
    """Приоритет handoff"""

    LOW = 1
    MEDIUM = 5
    HIGH = 7
    CRITICAL = 10


@dataclass
class Handoff:
    """
    Явный handoff между агентами

    Структурированная передача задачи с контекстом
    """

    handoff_id: str
    from_agent: str
    to_agent: str
    task: str
    context: Dict[str, Any]  # Структурированный контекст
    expected_output: str  # Ожидаемый результат
    deadline: datetime
    priority: HandoffPriority = HandoffPriority.MEDIUM
    status: HandoffStatus = HandoffStatus.PENDING

    # Метаданные
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Результат
    result: Optional[Any] = None
    error: Optional[str] = None

    # Валидация
    validation_schema: Optional[Dict] = None
    validation_result: Optional[Dict] = None

    def validate(self) -> bool:
        """
        Валидация handoff по контракту (Singularity 26.2)
        [SINGULARITY 28.0] Hard-Contract Enforcement: Raises ValueError on failure.
        """
        if not self.from_agent or not self.to_agent:
            self.error = "from_agent и to_agent обязательны"
            raise ValueError(self.error)

        if not self.task:
            self.error = "task обязателен"
            raise ValueError(self.error)

        if self.deadline < datetime.now(timezone.utc):
            self.error = "deadline в прошлом"
            raise ValueError(self.error)

        # [SINGULARITY 28.0] Hard-Contract Enforcement
        if self.validation_schema:
            try:
                import jsonschema

                jsonschema.validate(instance=self.context, schema=self.validation_schema)
                logger.info(f"✅ Handoff {self.handoff_id} validated against full contract.")
            except ImportError:
                # Simple validation if jsonschema is missing
                required = self.validation_schema.get("required", [])
                for field in required:
                    if field not in self.context:
                        self.error = f"Contract violation: missing required field '{field}'"
                        logger.warning(
                            f"❌ Handoff {self.handoff_id} contract violation: {self.error}"
                        )
                        raise ValueError(self.error)
            except Exception as e:
                self.error = f"Contract validation failed: {e}"
                logger.error(f"❌ Handoff {self.handoff_id} contract violation: {e}")
                raise ValueError(self.error)
        elif "contract" in self.context:
            # Fallback: если схема передана внутри контекста
            try:
                import jsonschema

                jsonschema.validate(instance=self.context, schema=self.context["contract"])
                logger.info(f"✅ Handoff {self.handoff_id} validated against inline contract.")
            except Exception as e:
                self.error = f"Inline contract validation failed: {e}"
                logger.error(f"❌ Handoff {self.handoff_id} inline contract violation: {e}")
                raise ValueError(self.error)

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        return {
            "handoff_id": self.handoff_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "task": self.task,
            "context": self.context,
            "expected_output": self.expected_output,
            "deadline": self.deadline.isoformat(),
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
        }


class HandoffManager:
    """
    Менеджер явных handoffs

    Управляет передачей задач между агентами
    """

    def __init__(self):
        self.handoffs: Dict[str, Handoff] = {}  # handoff_id -> Handoff
        self.handoff_history: List[Handoff] = []

    def create_handoff(
        self,
        from_agent: str,
        to_agent: str,
        task: str,
        context: Dict[str, Any],
        expected_output: str,
        deadline: Optional[datetime] = None,
        priority: HandoffPriority = HandoffPriority.MEDIUM,
    ) -> Handoff:
        """
        Создать явный handoff

        Args:
            from_agent: От кого
            to_agent: Кому
            task: Задача
            context: Контекст (структурированный)
            expected_output: Ожидаемый результат
            deadline: Дедлайн (по умолчанию +1 час)
            priority: Приоритет

        Returns:
            Handoff
        """
        import uuid

        handoff_id = f"handoff_{uuid.uuid4().hex[:12]}"

        if deadline is None:
            deadline = datetime.now(timezone.utc) + timedelta(hours=1)

        handoff = Handoff(
            handoff_id=handoff_id,
            from_agent=from_agent,
            to_agent=to_agent,
            task=task,
            context=context,
            expected_output=expected_output,
            deadline=deadline,
            priority=priority,
        )

        # Валидация
        if not handoff.validate():
            raise ValueError(f"Invalid handoff: {handoff.error}")

        self.handoffs[handoff_id] = handoff
        logger.info(f"📋 Создан handoff: {from_agent} → {to_agent} ({handoff_id})")

        return handoff

    def get_handoff(self, handoff_id: str) -> Optional[Handoff]:
        """Получить handoff по ID"""
        return self.handoffs.get(handoff_id)

    def start_handoff(self, handoff_id: str) -> bool:
        """Начать выполнение handoff"""
        handoff = self.handoffs.get(handoff_id)
        if not handoff:
            return False

        if handoff.status != HandoffStatus.PENDING:
            logger.warning(f"⚠️ Handoff {handoff_id} уже не в статусе PENDING")
            return False

        handoff.status = HandoffStatus.IN_PROGRESS
        handoff.started_at = datetime.now(timezone.utc)
        logger.info(f"▶️ Handoff {handoff_id} начат")
        return True

    def complete_handoff(
        self, handoff_id: str, result: Any, validation_result: Optional[Dict] = None
    ) -> bool:
        """Завершить handoff"""
        handoff = self.handoffs.get(handoff_id)
        if not handoff:
            return False

        handoff.status = HandoffStatus.COMPLETED
        handoff.completed_at = datetime.now(timezone.utc)
        handoff.result = result
        handoff.validation_result = validation_result

        # Перемещаем в историю
        self.handoff_history.append(handoff)
        del self.handoffs[handoff_id]

        logger.info(f"✅ Handoff {handoff_id} завершен")
        return True

    def fail_handoff(self, handoff_id: str, error: str) -> bool:
        """Пометить handoff как неудачный"""
        handoff = self.handoffs.get(handoff_id)
        if not handoff:
            return False

        handoff.status = HandoffStatus.FAILED
        handoff.completed_at = datetime.now(timezone.utc)
        handoff.error = error

        # Перемещаем в историю
        self.handoff_history.append(handoff)
        del self.handoffs[handoff_id]

        logger.error(f"❌ Handoff {handoff_id} провален: {error}")
        return True

    def get_pending_handoffs(self, agent_name: Optional[str] = None) -> List[Handoff]:
        """Получить ожидающие handoffs (для агента)"""
        handoffs = [h for h in self.handoffs.values() if h.status == HandoffStatus.PENDING]

        if agent_name:
            handoffs = [h for h in handoffs if h.to_agent == agent_name]

        # Сортируем по приоритету и дедлайну
        handoffs.sort(key=lambda h: (h.priority.value, h.deadline), reverse=True)

        return handoffs

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику handoffs"""
        return {
            "pending": len(
                [h for h in self.handoffs.values() if h.status == HandoffStatus.PENDING]
            ),
            "in_progress": len(
                [h for h in self.handoffs.values() if h.status == HandoffStatus.IN_PROGRESS]
            ),
            "completed": len(
                [h for h in self.handoff_history if h.status == HandoffStatus.COMPLETED]
            ),
            "failed": len([h for h in self.handoff_history if h.status == HandoffStatus.FAILED]),
            "total": len(self.handoff_history) + len(self.handoffs),
        }


# Глобальный менеджер handoffs
_handoff_manager: Optional[HandoffManager] = None


def get_handoff_manager() -> HandoffManager:
    """Получить глобальный менеджер handoffs"""
    global _handoff_manager
    if _handoff_manager is None:
        _handoff_manager = HandoffManager()
    return _handoff_manager


# ---------------------------------------------------------------------------
# Детерминированный роутер — НЕ зависит от LLM-тегов
# Принцип: на основе category/keywords в описании выбираем следующего эксперта
# ---------------------------------------------------------------------------

# Маппинг: (паттерны в описании) → (эксперт-получатель, приоритет)
_DETERMINISTIC_ROUTES: List[Dict] = [
    {
        "keywords": [
            "тест",
            "test",
            "pytest",
            "coverage",
            "проверь работу",
            "unit test",
            "integration test",
        ],
        "expert": "Анна",
        "reason": "QA проверка — автоматический handoff к тестировщику",
        "priority": HandoffPriority.HIGH,
    },
    {
        "keywords": [
            "deploy",
            "деплой",
            "docker",
            "kubernetes",
            "k8s",
            "nginx",
            "CI/CD",
            "restart",
            "rollout",
        ],
        "expert": "Сергей",
        "reason": "DevOps задача — автоматический handoff к DevOps",
        "priority": HandoffPriority.HIGH,
    },
    {
        "keywords": [
            "безопасност",
            "security",
            "уязвимост",
            "sql injection",
            "xss",
            "csrf",
            "audit безопасн",
        ],
        "expert": "Алексей",
        "reason": "Security audit — автоматический handoff к аудитору",
        "priority": HandoffPriority.CRITICAL,
    },
    {
        "keywords": [
            "метрики",
            "backtest",
            "sharpe",
            "drawdown",
            "аналитик",
            "отчёт",
            "отчет",
            "статистик",
        ],
        "expert": "Максим",
        "reason": "Аналитика — автоматический handoff к дата-аналитику",
        "priority": HandoffPriority.MEDIUM,
    },
    {
        "keywords": [
            "ml ",
            "модель",
            "обучени",
            "feature engineering",
            "pytorch",
            "tensorflow",
            "трейн",
        ],
        "expert": "Дмитрий",
        "reason": "ML задача — автоматический handoff к ML-инженеру",
        "priority": HandoffPriority.MEDIUM,
    },
]


def detect_deterministic_handoff(
    from_agent: str,
    task_description: str,
    task_result: str = "",
    category: str = "general",
) -> Optional[Handoff]:
    """
    Детерминированный handoff без LLM.

    Анализирует описание/результат задачи по ключевым словам и создаёт
    handoff к нужному эксперту. Не нужны LLM-теги в тексте ответа.

    Returns:
        Handoff объект если найдено совпадение, иначе None
    """
    text = (task_description + " " + task_result + " " + category).lower()

    for route in _DETERMINISTIC_ROUTES:
        if any(kw.lower() in text for kw in route["keywords"]):
            to_agent = route["expert"]
            # Не handoff-им сами себе
            if to_agent == from_agent:
                continue

            mgr = get_handoff_manager()
            handoff = mgr.create_handoff(
                from_agent=from_agent,
                to_agent=to_agent,
                task=f"[AUTO-HANDOFF] {task_description[:300]}",
                context={
                    "original_task": task_description[:500],
                    "partial_result": task_result[:500],
                    "category": category,
                    "auto_route_reason": route["reason"],
                },
                expected_output=f"Результат обработки задачи экспертом {to_agent}",
                priority=route["priority"],
            )
            logger.info(
                f"🔀 [DETERMINISTIC HANDOFF] {from_agent} → {to_agent} | "
                f"Причина: {route['reason']} | ID: {handoff.handoff_id}"
            )
            return handoff

    return None
    return _handoff_manager
