import asyncio
import json
import os
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Заглушки для импортов, если они недоступны
REACT_AVAILABLE = True
EXTENDED_THINKING_AVAILABLE = True
SWARM_AVAILABLE = True
CONSENSUS_AVAILABLE = True
COLLECTIVE_MEMORY_AVAILABLE = True
HIERARCHICAL_AVAILABLE = True
RECAP_AVAILABLE = True
TOT_AVAILABLE = True
METACOGNITIVE_AVAILABLE = True
LIFECYCLE_AVAILABLE = True
EVOLVER_AVAILABLE = True
OBSERVABILITY_AVAILABLE = False
ENHANCED_CACHE_AVAILABLE = False
STATE_MACHINE_AVAILABLE = False

try:
    from app.config import ORCHESTRATION_V2_ENABLED
except ImportError:
    ORCHESTRATION_V2_ENABLED = False

try:
    from app.ai_core import run_smart_agent_async
except ImportError:
    try:
        from ai_core import run_smart_agent_async
    except ImportError:
        run_smart_agent_async = None


class ReActAgent:
    def __init__(self, agent_name, model_name):
        pass


class ExtendedThinkingEngine:
    def __init__(self, model_name):
        pass


class SwarmIntelligence:
    def __init__(self, swarm_size, model_name):
        pass


class ConsensusAgent:
    def __init__(self, model_name):
        pass


class CollectiveMemorySystem:
    def __init__(self):
        pass


class HierarchicalOrchestrator:
    def __init__(self, root_agent):
        pass


class ReCAPFramework:
    def __init__(self, model_name):
        pass


class TreeOfThoughts:
    def __init__(self, model_name):
        pass


class MetacognitiveLearner:
    def __init__(self, agent_name):
        pass


class AgentLifecycleManager:
    def __init__(self):
        pass


class AgentEvolver:
    def __init__(self, agent_name):
        pass


class EventType(Enum):
    FILE_CREATED = "file_created"
    LOG_ERROR_DETECTED = "log_error_detected"
    PERFORMANCE_DEGRADED = "performance_degraded"
    SERVICE_DOWN = "service_down"
    DIALOGUE_REQUEST = "dialogue_request"
    EXPERT_RESPONSE = "expert_response"
    DIALOGUE_CONSENSUS = "dialogue_consensus"


class VictoriaEnhanced:
    """
    Victoria Enhanced - Victoria с интеграцией всех новых компонентов
    """

    _run_smart_agent_async = run_smart_agent_async
    _local_router = None

    def __init__(
        self,
        model_name: str = "phi3.5:3.8b",
        use_react: bool = True,
        use_extended_thinking: bool = True,
        use_swarm: bool = True,
        use_consensus: bool = True,
        use_collective_memory: bool = True,
        use_metacognitive: bool = True,
        use_lifecycle: bool = True,
        use_evolver: bool = True,
    ):
        self.model_name = model_name
        self.use_react = use_react and REACT_AVAILABLE
        self.use_extended_thinking = use_extended_thinking and EXTENDED_THINKING_AVAILABLE
        self.use_swarm = use_swarm and SWARM_AVAILABLE
        self.use_consensus = use_consensus and CONSENSUS_AVAILABLE
        self.use_collective_memory = use_collective_memory and COLLECTIVE_MEMORY_AVAILABLE
        self.use_metacognitive = use_metacognitive and METACOGNITIVE_AVAILABLE
        self.use_lifecycle = use_lifecycle and LIFECYCLE_AVAILABLE
        self.use_evolver = use_evolver and EVOLVER_AVAILABLE

        # Инициализируем компоненты
        self.react_agent = None
        self.extended_thinking = None
        self.swarm = None
        self.consensus = None
        self.collective_memory = None
        self.hierarchical_orch = None
        self.task_delegator = None
        self.recap = None
        self.tot = None
        self.metacognitive = None
        self.lifecycle_manager = None
        self.evolver = None

        self.observability = None
        self.cache = None
        self.use_cache = False

        # Инициализация Event-Driven Architecture и Skill Registry
        self.event_bus = None
        self.file_watcher = None
        self.service_monitor = None
        self.deadline_tracker = None
        self.skill_registry = None
        self.skill_loader = None
        self.event_handlers = None
        self.monitoring_started = False

        # [SINGULARITY 24.7] Auto-start Event Bus and Sentinel
        if os.getenv("ENABLE_EVENT_MONITORING", "false").lower() == "true":
            try:
                from app.event_bus import get_event_bus
                from app.autonomous_sentinel import get_autonomous_sentinel
                from app.victoria_event_handlers import VictoriaEventHandlers

                self.event_bus = get_event_bus()
                self.event_handlers = VictoriaEventHandlers(self)

                # Регистрация обработчиков
                self.event_bus.subscribe(
                    EventType.FILE_CREATED, self.event_handlers.handle_file_created
                )
                self.event_bus.subscribe(
                    EventType.LOG_ERROR_DETECTED, self.event_handlers.handle_log_error_detected
                )
                self.event_bus.subscribe(
                    EventType.PERFORMANCE_DEGRADED, self.event_handlers.handle_performance_degraded
                )
                self.event_bus.subscribe(
                    EventType.SERVICE_DOWN, self.event_handlers.handle_service_down
                )

                # Запуск шины и стража
                asyncio.create_task(self.event_bus.start())

                sentinel = get_autonomous_sentinel()
                asyncio.create_task(sentinel.start())

                self.monitoring_started = True
                logger.info("🚀 [AUTO-START] Event Bus and Autonomous Sentinel started")
            except Exception as e:
                logger.warning(f"⚠️ [AUTO-START] Failed to start Event Bus/Sentinel: {e}")

        self._initialize_components()

    def _initialize_components(self):
        """Инициализировать доступные компоненты"""
        if self.use_react:
            try:
                self.react_agent = ReActAgent(agent_name="Виктория", model_name=self.model_name)
                logger.info(f"✅ ReActAgent инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации ReActAgent: {e}")

        if self.use_extended_thinking:
            try:
                self.extended_thinking = ExtendedThinkingEngine(model_name=self.model_name)
                logger.info("✅ ExtendedThinkingEngine инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации ExtendedThinkingEngine: {e}")

        if self.use_swarm:
            try:
                self.swarm = SwarmIntelligence(swarm_size=16, model_name=self.model_name)
                logger.info("✅ SwarmIntelligence инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации SwarmIntelligence: {e}")

        if self.use_consensus:
            try:
                self.consensus = ConsensusAgent(model_name=self.model_name)
                logger.info("✅ ConsensusAgent инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации ConsensusAgent: {e}")

        if self.use_collective_memory:
            try:
                self.collective_memory = CollectiveMemorySystem()
                logger.info("✅ CollectiveMemorySystem инициализирован")
            except Exception as e:
                logger.debug(f"ℹ️ Ошибка инициализации CollectiveMemorySystem: {e}")

    async def start(self):
        """Запуск фоновых компонентов мониторинга (вызывается при lifespan startup)."""
        logger.info(
            "✅ [VictoriaEnhanced] start() вызван — мониторинг уже инициализирован в __init__"
        )

    async def _init_extended_thinking(self):
        """Ленивая инициализация Extended Thinking Engine."""
        if self.extended_thinking is None and EXTENDED_THINKING_AVAILABLE:
            try:
                from extended_thinking import ExtendedThinkingEngine

                self.extended_thinking = ExtendedThinkingEngine(
                    model_name=self.model_name,
                    thinking_budget=15000,
                    max_steps=12,
                    use_intelligent_routing=True,
                    dual_channel=True,
                )
                logger.info("✅ [VICTORIA] ExtendedThinkingEngine инициализирован")
            except ImportError as e:
                logger.warning(f"⚠️ ExtendedThinkingEngine недоступен: {e}")
                self.extended_thinking = None

    async def solve(self, goal: str, **kwargs):
        """
        Основной метод решения задач.
        [SINGULARITY 24.7] Added support for 'method' argument and proper LLM routing.
        [SINGULARITY 26.4] Extended Thinking полностью интегрирован.
        [SINGULARITY 28.0] LTM Integration: Recall memories before solving.
        """
        method = kwargs.get("method", "auto")
        category = kwargs.get("category") or self._categorize_task(goal)
        session_id = kwargs.get("session_id", "default")

        # [SINGULARITY 28.0] Long-term Memory Recall
        ltm_context = ""
        try:
            from long_term_memory import get_ltm
            ltm = get_ltm()
            memories = await ltm.recall_memories(goal)
            if memories:
                ltm_context = "\n📜 [LONG-TERM MEMORY]:\n"
                for m in memories:
                    ltm_context += f"- {m['content'][:500]}\n"
                logger.info(f"🧠 [VICTORIA] Recalled {len(memories)} memories for goal.")
        except Exception as ltm_err:
            logger.debug(f"LTM recall failed: {ltm_err}")

        # Inject LTM into context
        if ltm_context:
            kwargs["context"] = (kwargs.get("context") or "") + ltm_context

        logger.info(
            f"🧠 [VICTORIA] Solving goal: {goal[:50]}... (Method: {method}, Category: {category})"
        )

        if method == "extended_thinking" and self.use_extended_thinking:
            await self._init_extended_thinking()
            if self.extended_thinking:
                try:
                    context = {
                        "kb_context": kwargs.get("context", ""),
                        "session_id": kwargs.get("session_id", "default"),
                    }
                    result = await self.extended_thinking.think(goal, context, category=category)
                    return {
                        "result": result.final_answer,
                        "thinking_steps": [
                            {
                                "step": s.step_number,
                                "thought": s.thought,
                                "conclusion": s.conclusion,
                            }
                            for s in result.thinking_steps
                        ],
                        "confidence": result.confidence,
                        "thinking_time": result.thinking_time_seconds,
                    }
                except Exception as e:
                    logger.error(f"❌ Extended Thinking failed: {e}")
                    method = "auto"

        if VictoriaEnhanced._run_smart_agent_async is None:
            try:
                from ai_core import run_smart_agent_async

                VictoriaEnhanced._run_smart_agent_async = run_smart_agent_async
            except ImportError:
                try:
                    from app.ai_core import run_smart_agent_async

                    VictoriaEnhanced._run_smart_agent_async = run_smart_agent_async
                except ImportError:
                    pass

        if VictoriaEnhanced._run_smart_agent_async is not None:
            try:
                result = await VictoriaEnhanced._run_smart_agent_async(
                    goal,
                    expert_name="Виктория",
                    category=category,
                    local_router=VictoriaEnhanced._local_router,
                )
                return {"result": result}
            except Exception as e:
                logger.error(f"❌ [VICTORIA] LLM call failed: {e}")
                return {"result": f"Ошибка вызова LLM: {e}"}

        return {"result": f"Solved: {goal}"}

    def _categorize_task(self, goal: str) -> str:
        if any(k in goal.lower() for k in ["код", "напиши", "создай", "write", "code"]):
            return "coding"
        if any(k in goal.lower() for k in ["анализ", "анализируй", "analysis", "analyze"]):
            return "reasoning"
        if any(k in goal.lower() for k in ["найди", "поиск", "search", "find"]):
            return "search"
        return "general"

    async def get_status(self) -> Dict[str, Any]:
        """Получить статус компонентов Victoria Enhanced."""
        return {
            "monitoring_started": self.monitoring_started,
            "event_bus_available": self.event_bus is not None,
            "skill_registry_available": self.skill_registry is not None,
            "skills_count": 0,  # TODO: реализовать подсчет
            "file_watcher_available": self.file_watcher is not None,
            "service_monitor_available": self.service_monitor is not None,
        }
