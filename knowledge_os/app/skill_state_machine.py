"""
Skill State Machine - LangGraph state machines для обработки событий
Основано на LangGraph patterns: TypedDict/Pydantic states, persistence, checkpoints
Интегрируется с victoria_event_handlers.py
"""

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypedDict

try:
    from app.event_bus import Event, EventType
except ImportError:
    from event_bus import Event, EventType

logger = logging.getLogger(__name__)


class StateNode(Enum):
    """Узлы state machine (LangGraph pattern)"""

    START = "start"
    ANALYZE = "analyze"
    PROCESS = "process"
    VALIDATE = "validate"
    EXECUTE = "execute"
    WAIT_APPROVAL = "wait_approval"
    COMPLETE = "complete"
    FAIL = "fail"
    RETRY = "retry"


class MachineState(TypedDict):
    """Состояние state machine (LangGraph TypedDict pattern)"""

    event: Dict[str, Any]
    current_node: str
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    checkpoints: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    retry_count: int
    max_retries: int
    timestamp: str


@dataclass
class StateMachineConfig:
    """Конфигурация state machine"""

    max_retries: int = 3
    checkpoint_interval: int = 5  # секунд
    enable_persistence: bool = True
    persistence_path: Optional[str] = None


class SkillStateMachine:
    """
    LangGraph-style state machine для обработки событий skills

    Основано на:
    - LangGraph patterns (TypedDict states, persistence, checkpoints)
    - Microsoft AutoGen v0.4 (event-driven, async)
    - Clawdbot proactive actions
    """

    def __init__(self, config: Optional[StateMachineConfig] = None):
        """
        Инициализация state machine

        Args:
            config: Конфигурация state machine
        """
        self.config = config or StateMachineConfig()
        self.nodes: Dict[str, Callable] = {}
        self.edges: Dict[str, List[str]] = {}
        self.state_history: Dict[str, List[MachineState]] = {}
        self.checkpoints: Dict[str, MachineState] = {}

        # Настраиваем persistence
        if self.config.enable_persistence:
            if self.config.persistence_path is None:
                persistence_dir = os.path.expanduser("~/.atra/state_machines")
                os.makedirs(persistence_dir, exist_ok=True)
                self.config.persistence_path = persistence_dir
            logger.info(f"💾 Persistence включен: {self.config.persistence_path}")

        # Регистрируем узлы
        self._register_nodes()

        # Регистрируем переходы
        self._register_edges()

        logger.info("✅ Skill State Machine инициализирован")

    def _register_nodes(self):
        """Регистрировать узлы state machine"""
        self.nodes[StateNode.START.value] = self._node_start
        self.nodes[StateNode.ANALYZE.value] = self._node_analyze
        self.nodes[StateNode.PROCESS.value] = self._node_process
        self.nodes[StateNode.VALIDATE.value] = self._node_validate
        self.nodes[StateNode.EXECUTE.value] = self._node_execute
        self.nodes[StateNode.WAIT_APPROVAL.value] = self._node_wait_approval
        self.nodes[StateNode.COMPLETE.value] = self._node_complete
        self.nodes[StateNode.FAIL.value] = self._node_fail
        self.nodes[StateNode.RETRY.value] = self._node_retry

    def _register_edges(self):
        """Регистрировать переходы между узлами"""
        # START -> ANALYZE
        self.edges[StateNode.START.value] = [StateNode.ANALYZE.value]

        # ANALYZE -> PROCESS или VALIDATE
        self.edges[StateNode.ANALYZE.value] = [StateNode.PROCESS.value, StateNode.VALIDATE.value]

        # PROCESS -> VALIDATE
        self.edges[StateNode.PROCESS.value] = [StateNode.VALIDATE.value]

        # VALIDATE -> EXECUTE или WAIT_APPROVAL
        self.edges[StateNode.VALIDATE.value] = [
            StateNode.EXECUTE.value,
            StateNode.WAIT_APPROVAL.value,
        ]

        # EXECUTE -> COMPLETE или RETRY или FAIL
        self.edges[StateNode.EXECUTE.value] = [
            StateNode.COMPLETE.value,
            StateNode.RETRY.value,
            StateNode.FAIL.value,
        ]

        # WAIT_APPROVAL -> EXECUTE или FAIL
        self.edges[StateNode.WAIT_APPROVAL.value] = [StateNode.EXECUTE.value, StateNode.FAIL.value]

        # RETRY -> EXECUTE или FAIL
        self.edges[StateNode.RETRY.value] = [StateNode.EXECUTE.value, StateNode.FAIL.value]

        # COMPLETE и FAIL - конечные узлы
        self.edges[StateNode.COMPLETE.value] = []
        self.edges[StateNode.FAIL.value] = []

    async def _node_start(self, state: MachineState) -> MachineState:
        """Узел START - инициализация"""
        logger.info("🚀 State Machine: START")
        state["current_node"] = StateNode.START.value
        state["timestamp"] = datetime.now(timezone.utc).isoformat()
        state["retry_count"] = 0
        state["max_retries"] = self.config.max_retries
        state["checkpoints"] = []
        state["metadata"] = {}

        # Создаем первый checkpoint
        await self._create_checkpoint(state)

        return state

    async def _node_analyze(self, state: MachineState) -> MachineState:
        """Узел ANALYZE - анализ события"""
        logger.info("🔍 State Machine: ANALYZE")
        state["current_node"] = StateNode.ANALYZE.value

        event_data = state.get("event", {})
        event_type = event_data.get("event_type")

        # Анализируем тип события
        analysis = {
            "event_type": event_type,
            "requires_processing": True,
            "requires_validation": True,
            "requires_approval": False,
        }

        # Определяем, нужна ли валидация или одобрение
        if event_type in [EventType.SKILL_NEEDED.value, EventType.SERVICE_DOWN.value]:
            analysis["requires_approval"] = True

        state["metadata"]["analysis"] = analysis
        await self._create_checkpoint(state)

        return state

    async def _node_process(self, state: MachineState) -> MachineState:
        """Узел PROCESS - обработка события"""
        logger.info("⚙️ State Machine: PROCESS")
        state["current_node"] = StateNode.PROCESS.value

        event_data = state.get("event", {})
        event_type = event_data.get("event_type")

        # Обрабатываем событие в зависимости от типа
        processing_result = {"processed": True, "action": "processed"}

        if event_type == EventType.FILE_CREATED.value:
            processing_result["action"] = "file_analyzed"
        elif event_type == EventType.SERVICE_DOWN.value:
            processing_result["action"] = "service_restart_initiated"
        elif event_type == EventType.SKILL_NEEDED.value:
            processing_result["action"] = "skill_discovery_initiated"

        state["metadata"]["processing"] = processing_result
        await self._create_checkpoint(state)

        return state

    async def _node_validate(self, state: MachineState) -> MachineState:
        """Узел VALIDATE - валидация"""
        logger.info("✅ State Machine: VALIDATE")
        state["current_node"] = StateNode.VALIDATE.value

        # Валидация данных события
        event_data = state.get("event", {})
        validation_result = {"valid": True, "errors": []}

        # Проверяем наличие обязательных полей
        if not event_data.get("event_type"):
            validation_result["valid"] = False
            validation_result["errors"].append("event_type отсутствует")

        if not event_data.get("payload"):
            validation_result["valid"] = False
            validation_result["errors"].append("payload отсутствует")

        state["metadata"]["validation"] = validation_result
        await self._create_checkpoint(state)

        return state

    async def _node_execute(self, state: MachineState) -> MachineState:
        """Узел EXECUTE - выполнение действия"""
        logger.info("🎯 State Machine: EXECUTE")
        state["current_node"] = StateNode.EXECUTE.value

        # Выполняем действие (заглушка - в реальности здесь будет вызов handler)
        execution_result = {"success": True, "result": "Action executed successfully"}

        # Симулируем возможную ошибку
        if state.get("retry_count", 0) > 0:
            execution_result["success"] = True  # После retry успешно

        state["result"] = execution_result
        await self._create_checkpoint(state)

        return state

    async def _node_wait_approval(self, state: MachineState) -> MachineState:
        """Узел WAIT_APPROVAL - ожидание одобрения"""
        logger.info("⏳ State Machine: WAIT_APPROVAL")
        state["current_node"] = StateNode.WAIT_APPROVAL.value

        # В реальности здесь будет ожидание одобрения от пользователя
        # Пока симулируем автоматическое одобрение
        approval_result = {"approved": True, "approved_at": datetime.now(timezone.utc).isoformat()}

        state["metadata"]["approval"] = approval_result
        await self._create_checkpoint(state)

        return state

    async def _node_complete(self, state: MachineState) -> MachineState:
        """Узел COMPLETE - завершение"""
        logger.info("✅ State Machine: COMPLETE")
        state["current_node"] = StateNode.COMPLETE.value
        state["timestamp"] = datetime.now(timezone.utc).isoformat()

        await self._create_checkpoint(state)
        await self._persist_state(state)

        return state

    async def _node_fail(self, state: MachineState) -> MachineState:
        """Узел FAIL - ошибка"""
        logger.error("❌ State Machine: FAIL")
        state["current_node"] = StateNode.FAIL.value
        state["timestamp"] = datetime.now(timezone.utc).isoformat()

        await self._create_checkpoint(state)
        await self._persist_state(state)

        return state

    async def _node_retry(self, state: MachineState) -> MachineState:
        """Узел RETRY - повторная попытка"""
        retry_count = state.get("retry_count", 0) + 1
        max_retries = state.get("max_retries", self.config.max_retries)

        if retry_count > max_retries:
            logger.warning(f"⚠️ Достигнут лимит retry: {max_retries}")
            state["current_node"] = StateNode.FAIL.value
            state["error"] = f"Достигнут лимит retry: {max_retries}"
            return await self._node_fail(state)

        logger.info(f"🔄 State Machine: RETRY ({retry_count}/{max_retries})")
        state["current_node"] = StateNode.RETRY.value
        state["retry_count"] = retry_count

        await self._create_checkpoint(state)

        return state

    async def _create_checkpoint(self, state: MachineState):
        """Создать checkpoint (LangGraph pattern)"""
        checkpoint_id = f"{state.get('event', {}).get('event_id', 'unknown')}_{state.get('current_node', 'unknown')}_{datetime.now(timezone.utc).timestamp()}"

        # МОНСТР-ЛОГИКА: Предотвращаем Circular reference (циклические ссылки) в checkpoints
        # Копируем состояние, но удаляем из копии список checkpoints, чтобы не было рекурсии
        state_copy = dict(state)
        if "checkpoints" in state_copy:
            state_copy.pop("checkpoints")

        checkpoint = {
            "checkpoint_id": checkpoint_id,
            "state": state_copy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self.checkpoints[checkpoint_id] = state

        # Добавляем в историю
        event_id = state.get("event", {}).get("event_id", "unknown")
        if event_id not in self.state_history:
            self.state_history[event_id] = []
        self.state_history[event_id].append(state)

        # Сохраняем checkpoint в state
        if "checkpoints" not in state:
            state["checkpoints"] = []
        state["checkpoints"].append(checkpoint)

        logger.debug(f"💾 Checkpoint создан: {checkpoint_id}")

    async def _persist_state(self, state: MachineState):
        """Сохранить состояние на диск (persistence)"""
        if not self.config.enable_persistence:
            return

        try:
            event_id = state.get("event", {}).get("event_id", "unknown")
            filename = f"{event_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(self.config.persistence_path, filename)

            # МОНСТР-ЛОГИКА: Глубокая очистка от циклических ссылок перед сохранением
            def safe_serialize(obj, visited=None):
                if visited is None:
                    visited = set()

                obj_id = id(obj)
                if obj_id in visited:
                    return "<Circular Reference>"

                if isinstance(obj, dict):
                    visited.add(obj_id)
                    return {k: safe_serialize(v, visited) for k, v in obj.items()}
                elif isinstance(obj, list):
                    visited.add(obj_id)
                    return [safe_serialize(i, visited) for i in obj]
                elif isinstance(obj, (str, int, float, bool, type(None))):
                    return obj
                else:
                    return str(obj)

            safe_state = safe_serialize(state)

            # Сохраняем состояние
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(safe_state, f, indent=2, ensure_ascii=False)

            logger.debug(f"💾 Состояние сохранено: {filepath}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения состояния: {e}")

    async def restore_from_checkpoint(self, checkpoint_id: str) -> Optional[MachineState]:
        """Восстановить состояние из checkpoint"""
        checkpoint = self.checkpoints.get(checkpoint_id)
        if checkpoint:
            logger.info(f"🔄 Восстановлено состояние из checkpoint: {checkpoint_id}")
            return checkpoint

        # Пробуем загрузить с диска
        if self.config.enable_persistence:
            try:
                for filename in os.listdir(self.config.persistence_path):
                    if checkpoint_id in filename:
                        filepath = os.path.join(self.config.persistence_path, filename)
                        with open(filepath, encoding="utf-8") as f:
                            state = json.load(f)
                            logger.info(f"🔄 Восстановлено состояние с диска: {filepath}")
                            return state
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки состояния: {e}")

        return None

    def _get_next_node(self, current_node: str, state: MachineState) -> Optional[str]:
        """Определить следующий узел на основе условий"""
        next_nodes = self.edges.get(current_node, [])

        if not next_nodes:
            return None

        # Простая логика выбора следующего узла
        # В реальности здесь может быть более сложная логика на основе состояния

        if current_node == StateNode.ANALYZE.value:
            # ANALYZE -> PROCESS или VALIDATE
            analysis = state.get("metadata", {}).get("analysis", {})
            if analysis.get("requires_processing", True):
                return StateNode.PROCESS.value
            else:
                return StateNode.VALIDATE.value

        elif current_node == StateNode.VALIDATE.value:
            # VALIDATE -> EXECUTE или WAIT_APPROVAL
            validation = state.get("metadata", {}).get("validation", {})
            if not validation.get("valid", True):
                return StateNode.FAIL.value

            analysis = state.get("metadata", {}).get("analysis", {})
            if analysis.get("requires_approval", False):
                return StateNode.WAIT_APPROVAL.value
            else:
                return StateNode.EXECUTE.value

        elif current_node == StateNode.EXECUTE.value:
            # EXECUTE -> COMPLETE или RETRY или FAIL
            result = state.get("result", {})
            if result.get("success", False):
                return StateNode.COMPLETE.value
            else:
                retry_count = state.get("retry_count", 0)
                max_retries = state.get("max_retries", self.config.max_retries)
                if retry_count < max_retries:
                    return StateNode.RETRY.value
                else:
                    return StateNode.FAIL.value

        elif current_node == StateNode.RETRY.value:
            # RETRY -> EXECUTE
            return StateNode.EXECUTE.value

        elif current_node == StateNode.WAIT_APPROVAL.value:
            # WAIT_APPROVAL -> EXECUTE или FAIL
            approval = state.get("metadata", {}).get("approval", {})
            if approval.get("approved", False):
                return StateNode.EXECUTE.value
            else:
                return StateNode.FAIL.value

        # По умолчанию берем первый узел из списка
        return next_nodes[0] if next_nodes else None

    async def run(self, event: Event) -> MachineState:
        """
        Запустить state machine для обработки события

        Args:
            event: Событие для обработки

        Returns:
            Финальное состояние state machine
        """
        logger.info(f"🚀 Запуск State Machine для события: {event.event_type.value}")

        # Инициализируем состояние
        state: MachineState = {
            "event": {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "payload": event.payload,
                "source": event.source,
            },
            "current_node": StateNode.START.value,
            "result": None,
            "error": None,
            "checkpoints": [],
            "metadata": {},
            "retry_count": 0,
            "max_retries": self.config.max_retries,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Запускаем выполнение
        current_node = StateNode.START.value
        max_iterations = 20  # Защита от бесконечных циклов
        iteration = 0

        while current_node and iteration < max_iterations:
            iteration += 1

            # Выполняем узел
            if current_node not in self.nodes:
                logger.error(f"❌ Узел {current_node} не найден")
                state["error"] = f"Узел {current_node} не найден"
                state["current_node"] = StateNode.FAIL.value
                break

            try:
                node_func = self.nodes[current_node]
                state = await node_func(state)

                # Проверяем, достигли ли конечного узла
                if current_node in [StateNode.COMPLETE.value, StateNode.FAIL.value]:
                    break

                # Определяем следующий узел
                next_node = self._get_next_node(current_node, state)
                if next_node is None:
                    logger.info("🏁 Достигнут конец workflow")
                    break

                current_node = next_node

            except Exception as e:
                logger.error(f"❌ Ошибка в узле {current_node}: {e}", exc_info=True)
                state["error"] = str(e)
                state["current_node"] = StateNode.FAIL.value
                break

        if iteration >= max_iterations:
            logger.warning(f"⚠️ Достигнут лимит итераций: {max_iterations}")
            state["error"] = f"Достигнут лимит итераций: {max_iterations}"
            state["current_node"] = StateNode.FAIL.value

        logger.info(f"✅ State Machine завершена: {state['current_node']}")
        return state

    def get_state_history(self, event_id: str) -> List[MachineState]:
        """Получить историю состояний для события"""
        return self.state_history.get(event_id, [])

    def get_checkpoint(self, checkpoint_id: str) -> Optional[MachineState]:
        """Получить checkpoint"""
        return self.checkpoints.get(checkpoint_id)


# Пример использования
async def main():
    """Пример использования Skill State Machine"""
    import logging

    logging.basicConfig(level=logging.INFO)

    # Создаем state machine
    config = StateMachineConfig(max_retries=3, enable_persistence=True)
    machine = SkillStateMachine(config)

    # Создаем тестовое событие
    try:
        from app.event_bus import Event, EventType
    except ImportError:
        from event_bus import Event, EventType

    event = Event(
        event_id="test_event_1",
        event_type=EventType.FILE_CREATED,
        payload={"file_path": "/tmp/test.py", "file_name": "test.py"},
        source="test",
    )

    # Запускаем state machine
    result = await machine.run(event)

    print(f"Результат: {result['current_node']}")
    print(f"Checkpoints: {len(result['checkpoints'])}")


if __name__ == "__main__":
    asyncio.run(main())
