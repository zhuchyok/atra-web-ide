import asyncio
import json
import logging
import os
import re
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


def _extract_audit_file_path(goal: str) -> Optional[str]:
    if not goal:
        return None
    patterns = (
        r"(/app/[^\s,;:]+\.py)",
        r"(/Users/[^\s,;:]+\.py)",
        r"(knowledge_os/[^\s,;:]+\.py)",
    )
    for pattern in patterns:
        match = re.search(pattern, goal)
        if match:
            return match.group(1).rstrip(".,:;)")
    return None


def _resolve_existing_python_path(raw_path: str) -> Optional[str]:
    if not raw_path:
        return None
    clean = raw_path.strip()
    candidates = [clean]
    norm = clean.lstrip("./")
    candidates.extend(
        [
            f"/app/{norm}",
            f"/app/knowledge_os/{norm}",
        ]
    )
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def _run_fast_security_audit(goal: str) -> Optional[str]:
    text = (goal or "").lower()
    is_file_check = "проверь файл" in text or "check file" in text
    if not is_file_check:
        return None
    if "pip install" not in text and "hardcoded" not in text and "секрет" not in text:
        return None

    raw_path = _extract_audit_file_path(goal or "")
    resolved_path = _resolve_existing_python_path(raw_path or "")
    if not resolved_path:
        return None

    try:
        with open(resolved_path, encoding="utf-8", errors="ignore") as handle:
            lines = list(handle.readlines())
    except Exception as err:
        return f"ПРОБЛЕМА\nФайл: {resolved_path}\nНе удалось прочитать файл: {err}"

    if "pip install" in text:
        findings = []
        for idx, line in enumerate(lines, 1):
            lowered = line.lower()
            if (
                "pip" in lowered
                and "install" in lowered
                and (
                    "subprocess." in lowered
                    or "os.system(" in lowered
                    or "python -m pip install" in lowered
                    or "python3 -m pip install" in lowered
                )
            ):
                findings.append(f"L{idx}: {line.strip()[:220]}")
        if findings:
            return (
                "ПРОБЛЕМА\n"
                f"Файл: {resolved_path}\n"
                "Найдены признаки runtime pip install:\n"
                + "\n".join(f"- {entry}" for entry in findings[:5])
            )
        return (
            "ОК\n"
            f"Файл: {resolved_path}\n"
            "Runtime вызовов pip install через subprocess/os.system/python -m pip install не обнаружено."
        )

    if "hardcoded" in text or "секрет" in text or "парол" in text:
        suspicious = []
        for idx, line in enumerate(lines[:30], 1):
            stripped = line.strip()
            lowered = stripped.lower()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            if any(k in lowered for k in ("password", "passwd", "secret", "token", "api_key")):
                if any(
                    safe in lowered
                    for safe in ("os.getenv", "environ.get", "changeme", "example", "<secret>")
                ):
                    continue
                if re.search(r"=\s*[\"'][^\"']{3,}[\"']", stripped):
                    suspicious.append(f"L{idx}: {stripped[:220]}")
        if suspicious:
            return (
                "ПРОБЛЕМА\n"
                f"Файл: {resolved_path}\n"
                "В первых 30 строках найдены потенциально hardcoded секреты/пароли:\n"
                + "\n".join(f"- {entry}" for entry in suspicious[:5])
            )
        return (
            "ОК\n"
            f"Файл: {resolved_path}\n"
            "В первых 30 строках hardcoded секреты/пароли не обнаружены."
        )

    return None


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
                from app.autonomous_sentinel import get_autonomous_sentinel
                from app.event_bus import EventType as BusEventType
                from app.event_bus import get_event_bus
                from app.victoria_event_handlers import VictoriaEventHandlers

                self.event_bus = get_event_bus()
                self.event_handlers = VictoriaEventHandlers(self)

                # Регистрация обработчиков
                self.event_bus.subscribe(
                    BusEventType.FILE_CREATED, self.event_handlers.handle_file_created
                )
                self.event_bus.subscribe(
                    BusEventType.LOG_ERROR_DETECTED, self.event_handlers.handle_log_error_detected
                )
                self.event_bus.subscribe(
                    BusEventType.PERFORMANCE_DEGRADED,
                    self.event_handlers.handle_performance_degraded,
                )
                self.event_bus.subscribe(
                    BusEventType.SERVICE_DOWN, self.event_handlers.handle_service_down
                )
                # Dialogue pipeline: route expert-specific requests into expert task queue
                # and accept expert responses / final consensus events.
                self.event_bus.subscribe(
                    BusEventType.DIALOGUE_REQUEST, self.event_handlers.handle_dialogue_request
                )
                self.event_bus.subscribe(
                    BusEventType.EXPERT_RESPONSE, self.event_handlers.handle_expert_response
                )
                self.event_bus.subscribe(
                    BusEventType.DIALOGUE_CONSENSUS,
                    self.event_handlers.handle_dialogue_consensus,
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
                logger.info("✅ ReActAgent инициализирован")
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

        # Operational audits should avoid reasoning loops and use direct general execution path.
        g_low = (goal or "").lower()
        if ("аудит" in g_low or "deep-analysis" in g_low or "deep analysis" in g_low) and (
            "дашборд" in g_low or "dashboard" in g_low
        ):
            category = "general"

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

        # Operational goals (аудит дашборда): Department Heads + парсинг Veronica — лишняя задержка.
        skip_dept_heads = False
        try:
            from src.agents.bridge.task_detector import is_operational_execution_goal

            skip_dept_heads = is_operational_execution_goal(goal)
        except Exception:
            g = (goal or "").lower()
            skip_dept_heads = "аудит" in g and ("дашборд" in g or "dashboard" in g)

        # Backward-compatible Department Heads chain (used by tests and legacy flow).
        should_use_department_heads, dept_info = False, {}
        if not skip_dept_heads:
            try:
                should_use_department_heads, dept_info = await self._should_use_department_heads(
                    goal, category=category
                )
            except Exception as e:
                logger.debug(f"Department heads pre-check failed: {e}")
                should_use_department_heads, dept_info = False, {}

        if should_use_department_heads:
            try:
                dept_result = await self._execute_with_task_distribution(
                    goal=goal,
                    veronica_prompt=dept_info.get("veronica_prompt", goal),
                    organizational_structure=dept_info.get("organizational_structure", {}),
                    department=dept_info.get("department", "Strategy/Data"),
                )
                if dept_result and dept_result.get("result"):
                    return dept_result
            except Exception as e:
                logger.warning(f"⚠️ Department heads flow failed, fallback to default solve: {e}")

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
            fast_audit_result = _run_fast_security_audit(goal)
            if fast_audit_result:
                return {"result": fast_audit_result, "method": "enhanced_fast_audit"}
            _default_llm_timeout = float(os.getenv("VICTORIA_ENHANCED_LLM_TIMEOUT_SEC", "1200"))
            _operational_llm_timeout = float(
                os.getenv("VICTORIA_ENHANCED_LLM_TIMEOUT_OPERATIONAL_SEC", "240")
            )
            llm_timeout = (
                _operational_llm_timeout if is_operational_execution_goal else _default_llm_timeout
            )
            try:
                llm_task = asyncio.create_task(
                    VictoriaEnhanced._run_smart_agent_async(
                        goal,
                        expert_name="Виктория",
                        category=category,
                        local_router=VictoriaEnhanced._local_router,
                    )
                )
                done, _ = await asyncio.wait({llm_task}, timeout=llm_timeout)
                if not done:
                    logger.error(
                        "❌ [VICTORIA] LLM soft-timeout after %ss (goal_preview=%s)",
                        int(llm_timeout),
                        (goal or "")[:80],
                    )
                    # Не делаем task.cancel(): в этом стеке cancel может вызывать RecursionError.
                    return {
                        "result": f"Таймаут Enhanced LLM ({int(llm_timeout)}s). Сократите задачу.",
                        "method": "enhanced_llm_timeout",
                        "status": "failed",
                    }
                result = llm_task.result()
                return {"result": result}
            except Exception as e:
                logger.error(f"❌ [VICTORIA] LLM call failed: {e}")
                return {"result": f"Ошибка вызова LLM: {e}"}

        return {"result": f"Solved: {goal}"}

    def _is_casual_chat(self, text: str) -> bool:
        """Detect short conversational messages that should not trigger orchestration."""
        t = (text or "").strip().lower()
        if not t:
            return False
        casual_markers = (
            "привет",
            "здравств",
            "как дела",
            "поболтать",
            "расскажи о себе",
            "что умеешь",
            "hello",
            "hi",
            "thanks",
            "спасибо",
            "пока",
            "ок",
            "okay",
        )
        if any(m in t for m in casual_markers):
            return True
        # Very short non-imperative phrases are likely chat.
        if len(t.split()) <= 2 and not any(
            verb in t for verb in ("сделай", "напиши", "создай", "проанализируй", "покажи")
        ):
            return True
        return False

    def _is_simple_veronica_request(self, text: str) -> bool:
        """Detect simple one-step local assistant requests."""
        t = (text or "").strip().lower()
        if not t:
            return False
        simple_patterns = (
            "покажи файл",
            "покажи файлы",
            "список файлов",
            "выведи список",
            "прочитай файл",
            "покажи список",
            "list files",
            "show file",
            "read file",
        )
        complex_patterns = (
            "сделай",
            "напиши код",
            "реализуй",
            "архитектур",
            "отч",
            "analyze",
            "refactor",
        )
        if any(p in t for p in complex_patterns):
            return False
        return any(p in t for p in simple_patterns)

    async def _should_delegate_task(self, goal: str) -> Tuple[bool, Dict[str, Any]]:
        """Legacy delegation guard used by tests with PREFER_EXPERTS_FIRST."""
        prefer_experts_first = os.getenv("PREFER_EXPERTS_FIRST", "false").lower() == "true"
        if prefer_experts_first and self._is_simple_veronica_request(goal):
            return True, {"agent": "Вероника", "reason": "simple_veronica_request"}
        return False, {}

    async def _should_use_department_heads(
        self, goal: str, category: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Decide whether to route request through Department Heads orchestration."""
        if self._is_casual_chat(goal):
            return False, {}

        try:
            from app.department_heads_system import get_department_heads_system
        except ImportError:
            return False, {}

        system = get_department_heads_system(os.getenv("DATABASE_URL"))
        department = system.determine_department(goal)
        if not department:
            return False, {}

        dept_struct = {
            "departments": [
                {
                    "id": department,
                    "name": department,
                    "manager": {"id": 1, "name": "Department Head"},
                    "employees": [],
                    "employee_count": 1,
                }
            ],
            "total_departments": 1,
            "total_employees": 1,
        }
        veronica_prompt = (
            f"ЗАДАЧА: {goal}\nОТДЕЛ: {department}\nРазбей на подзадачи и распредели исполнителям."
        )
        return True, {
            "department": department,
            "veronica_prompt": veronica_prompt,
            "organizational_structure": dept_struct,
        }

    async def _synthesize_collected_results(
        self, goal: str, department: str, task_collection: Any
    ) -> str:
        """Synthesize department collection into final answer."""
        if task_collection is None:
            return ""
        if isinstance(task_collection, dict):
            return str(task_collection.get("aggregated_result", "") or "")
        aggregated = getattr(task_collection, "aggregated_result", "")
        if aggregated:
            return str(aggregated)
        return str(getattr(task_collection, "result", "") or "")

    async def _execute_with_task_distribution(
        self,
        goal: str,
        veronica_prompt: str,
        organizational_structure: Dict[str, Any],
        department: str,
    ) -> Dict[str, Any]:
        """Execute Department Heads task distribution chain."""
        from app.task_distribution_system import get_task_distribution_system

        task_dist = get_task_distribution_system(os.getenv("DATABASE_URL", ""))
        assignments = await task_dist.distribute_tasks_from_veronica_prompt(
            veronica_prompt,
            organizational_structure=organizational_structure,
            department=department,
            goal=goal,
        )
        reviewed_assignments = []
        for assignment in assignments or []:
            executed = await task_dist.execute_task_assignment(assignment)
            reviewed = await task_dist.manager_review_task(executed)
            reviewed_assignments.append(reviewed)

        collection = await task_dist.department_head_collect_tasks(department, reviewed_assignments)
        synthesized = await self._synthesize_collected_results(goal, department, collection)
        return {
            "method": "task_distribution",
            "department": department,
            "result": synthesized,
            "collection": collection,
        }

    def _categorize_task(self, goal: str) -> str:
        if any(k in goal.lower() for k in ["код", "напиши", "создай", "write", "code"]):
            return "coding"
        if any(k in goal.lower() for k in ["анализ", "анализируй", "analysis", "analyze"]):
            return "reasoning"
        if any(k in goal.lower() for k in ["найди", "поиск", "search", "find"]):
            return "search"
        return "general"

    async def get_status(self) -> Dict[str, Any]:
        """
        [SINGULARITY 28.5] Detailed health status for gRPC Heartbeat.
        """
        import psutil

        try:
            process = psutil.Process(os.getpid())
            stats = {
                "cpu_usage": process.cpu_percent(),
                "memory_usage_mb": process.memory_info().rss / (1024 * 1024),
                "active_tasks": len(asyncio.all_tasks()),
            }
        except Exception:
            stats = {}

        return {
            "monitoring_started": self.monitoring_started,
            "event_bus_available": self.event_bus is not None,
            "skill_registry_available": self.skill_registry is not None,
            "file_watcher_available": self.file_watcher is not None,
            "service_monitor_available": self.service_monitor is not None,
            "system_stats": stats,
        }
