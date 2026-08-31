"""
[SINGULARITY CORE] AI Agent Coordination Module.
Handles caching, routing, knowledge retrieval (RAG), and consensus across agents.
Optimized for Hybrid Intelligence (Cloud Architect + Local Worker).
"""

import sys

# CRITICAL: Set recursion BEFORE any async operations to prevent deep recursion stack crashes
# Victoria's complex async pipeline with 200+ loggers needs this
if hasattr(sys, "setrecursionlimit"):
    sys.setrecursionlimit(3000)

import asyncio
import contextvars
import getpass
import inspect
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

# [SINGULARITY 29.5] Recursion Guard for Multi-Agent Loops
# Prevents IterativeDiscovery -> run_smart_agent -> IterativeDiscovery loops
_RECURSION_CONTEXT = contextvars.ContextVar(
    "recursion_context", default={"depth": 0, "discovery": False, "debate": False}
)

# Third-party imports with fallbacks
try:
    import asyncpg  # type: ignore
except ImportError:
    asyncpg = None  # type: ignore

try:
    import nest_asyncio  # type: ignore
except ImportError:
    nest_asyncio = None  # type: ignore

# Local project imports with fallbacks
try:
    from semantic_cache import SemanticAICache, get_embedding  # type: ignore
except ImportError:
    SemanticAICache = None  # type: ignore

# Environment flags
try:
    from env_flags import is_strict_local  # type: ignore
except ImportError:
    # Fallback если модуль не найден
    def is_strict_local():
        return os.getenv("STRICT_LOCAL", "").lower() in ("1", "true", "yes")

    async def get_embedding(text: str) -> Optional[List[float]]:
        return None


# [SINGULARITY 21.32] Prompt Master Integration
try:
    from memory_block import get_memory_block
    from session_context_manager import get_session_context_manager
    from token_auditor import audit_efficiency
except ImportError:
    get_memory_block = lambda x: ""
    audit_efficiency = lambda x: x
    get_session_context_manager = lambda: None


def _build_error_response(message: str) -> str:
    return message


def record_llm_request(**_kwargs) -> None:
    return None


# [SINGULARITY 22.1] Real-time Multi-Agent Debate
try:
    from consensus_agent import ConsensusAgent
except ImportError:
    ConsensusAgent = None

# [SINGULARITY 26.2] Swarm & Handoff Integration
try:
    from explicit_handoffs import get_handoff_manager
except ImportError:

    def get_handoff_manager():
        return None


# [SINGULARITY 22.8] Iterative Discovery
try:
    from iterative_discovery import IterativeDiscovery
except ImportError:
    IterativeDiscovery = None


try:
    from local_router import LocalAIRouter  # type: ignore
except ImportError:
    LocalAIRouter = None  # type: ignore

try:
    from redis_manager import RedisManager  # type: ignore
except ImportError:
    RedisManager = None  # type: ignore

try:
    from app.ollama_keep_alive_policy import get_keep_alive
except ImportError:

    def get_keep_alive(model, mlx_alive=True):
        return 300


try:
    from distillation_engine import KnowledgeDistiller  # type: ignore
except ImportError:
    KnowledgeDistiller = None  # type: ignore

try:
    from context_compressor import ContextCompressor  # type: ignore
except ImportError:

    class ContextCompressor:
        @staticmethod
        def compress_all(prompt: str) -> str:
            return prompt


try:
    from safety_checker import SafetyChecker  # type: ignore
except ImportError:
    SafetyChecker = None  # type: ignore

try:
    from veronica_web_researcher import VeronicaWebResearcher  # type: ignore
except ImportError:
    VeronicaWebResearcher = None  # type: ignore

try:
    from optimizers import (  # type: ignore
        BETokenManager,
        EmbeddingCache,
        FrugalPrompt,
        PredictiveCache,
        PromptOptimizer,
        get_betoken_manager,
    )
except ImportError:
    PromptOptimizer = None  # type: ignore
    EmbeddingCache = None  # type: ignore
    PredictiveCache = None  # type: ignore
    FrugalPrompt = None  # type: ignore
    BETokenManager = None  # type: ignore
    get_betoken_manager = None  # type: ignore

try:
    from parallel_request_processor import (  # type: ignore
        ParallelRequestProcessor,
        RequestSource,
        get_parallel_processor,
    )
except ImportError:
    ParallelRequestProcessor = None  # type: ignore
    RequestSource = None  # type: ignore
    get_parallel_processor = None  # type: ignore

try:
    from quality_assurance import QualityAssurance, QualityGate  # type: ignore
except ImportError:
    QualityAssurance = None  # type: ignore
    QualityGate = None  # type: ignore

try:
    from ml_router_data_collector import get_collector  # type: ignore
except ImportError:
    get_collector = None  # type: ignore

try:
    from batch_processor import get_batch_processor  # type: ignore
except ImportError:
    get_batch_processor = None  # type: ignore

try:
    from optimizers import ParallelProcessor  # type: ignore
except ImportError:
    ParallelProcessor = None  # type: ignore

try:
    from prompt_templates import format_prompt, get_prompt_template  # type: ignore
    from query_orchestrator import QueryOrchestrator, QueryType  # type: ignore
except ImportError:
    QueryOrchestrator = None  # type: ignore
    QueryType = None  # type: ignore
    get_prompt_template = None  # type: ignore
    format_prompt = None  # type: ignore

try:
    from feedback_collector import get_feedback_collector  # type: ignore
except ImportError:
    get_feedback_collector = None  # type: ignore

try:
    from ml_router_v2 import get_ml_router_v2  # type: ignore
except ImportError:
    get_ml_router_v2 = None  # type: ignore

try:
    from session_context_manager import get_session_context_manager  # type: ignore
except ImportError:
    get_session_context_manager = None  # type: ignore

try:
    from context_analyzer import ContextAnalyzer  # type: ignore
except ImportError:
    ContextAnalyzer = None  # type: ignore

try:
    from vision_processor import get_vision_processor  # type: ignore
except ImportError:
    get_vision_processor = None  # type: ignore

try:
    from circuit_breaker import CircuitBreakerOpenError, get_circuit_breaker  # type: ignore
except ImportError:
    get_circuit_breaker = None  # type: ignore
    CircuitBreakerOpenError = Exception

try:
    from disaster_recovery import SystemMode, get_disaster_recovery  # type: ignore
except ImportError:
    get_disaster_recovery = None  # type: ignore
    SystemMode = None

try:
    from tacit_knowledge_miner import TacitKnowledgeMiner  # type: ignore
except ImportError:
    TacitKnowledgeMiner = None  # type: ignore

try:
    from emotion_detector import EmotionDetector  # type: ignore
except ImportError:
    EmotionDetector = None  # type: ignore

try:
    from architecture_profiler import profile_function  # type: ignore
except ImportError:

    def profile_function(module_name: str):
        def decorator(func):
            return func

        return decorator


try:
    from traffic_mirror import get_traffic_mirror  # type: ignore
except ImportError:
    get_traffic_mirror = None

try:
    from shadow_execution_manager import ShadowExecutionManager
except ImportError:
    ShadowExecutionManager = None

try:
    from shadow_evaluator import ShadowEvaluator
except ImportError:
    ShadowEvaluator = None

try:
    from personality_manager import get_personality_manager
except ImportError:
    get_personality_manager = None


class ContextSwapper:
    """
    [SINGULARITY 14.2] Memory Guard (Redis Context Swapping).
    Swaps full contexts to Redis and replaces them with summaries to save tokens.
    """

    def __init__(self, redis_mgr=None, max_tokens: int = 8000):
        from redis_manager import redis_manager

        self.redis = redis_mgr or redis_manager
        self.max_tokens = max_tokens
        self.extractor = FactExtractor()

    async def swap_if_needed(self, context: str, key: str) -> str:
        """Swaps context if it exceeds token limit."""
        if not context or len(context) < self.max_tokens:
            return context

        logger.info(f"🔄 [SWAPPER] Context too long ({len(context)}), swapping to Redis: {key}")

        # 1. Store full context in Redis
        await self.redis.set_cache(f"swap:{key}", context, ttl=1800)

        # 2. Extract facts for active context
        summary = await self.extractor.extract_facts(
            context, context_description=f"Swapped context: {key}"
        )

        return f"[CONTEXT SWAPPED TO REDIS: {key}]\nSUMMARY:\n{summary}"


try:
    from episodic_memory import get_episodic_memory_manager
except ImportError:
    get_episodic_memory_manager = None

try:
    from multi_agent_debate import get_multi_agent_debate
except ImportError:
    get_multi_agent_debate = None

try:
    from autonomous_tool_creator import get_autonomous_tool_creator
except ImportError:
    get_autonomous_tool_creator = None

try:
    from mcts_planner import get_mcts_planner
except ImportError:
    get_mcts_planner = None

try:
    from autonomous_sentinel import get_autonomous_sentinel
except ImportError:
    get_autonomous_sentinel = None

try:
    from distillation_engine import get_distillation_engine
except ImportError:
    get_distillation_engine = None


class TeamDiscussionEngine:
    """
    [SINGULARITY 24.2] Local Team Discussion Engine.
    Simulates collective intelligence by generating multi-expert dialogues locally.
    """

    _expert_styles_cache: Dict[str, str] = {}
    _last_cache_time: float = 0
    CACHE_TTL = 3600  # 1 hour

    def __init__(self, router: Optional["LocalAIRouter"] = None):
        self.router = router

    def _get_expert_styles(self, expert_names: List[str]) -> str:
        """
        Extracts personality traits and styles for the requested experts.
        Uses caching to avoid redundant file reads.
        """
        current_time = time.time()
        if not self._expert_styles_cache or (current_time - self._last_cache_time > self.CACHE_TTL):
            self._refresh_styles_cache()

        styles = []
        for name in expert_names:
            # Try exact match or case-insensitive match
            style = self._expert_styles_cache.get(name)
            if not style:
                # Try to find by partial match (e.g. "Igor" in "Igor (Backend Developer)")
                for cache_key, cache_val in self._expert_styles_cache.items():
                    if name.lower() in cache_key.lower():
                        style = cache_val
                        break

            if style:
                styles.append(f"### {name} Style:\n{style}")
            else:
                styles.append(
                    f"### {name} Style:\nProfessional, technical, and focused on the task."
                )

        return "\n\n".join(styles)

    def _refresh_styles_cache(self):
        """Parses TEAM_PERSONALITIES.md and populates the cache."""
        try:
            # Try multiple potential locations for docs/TEAM_PERSONALITIES.md
            possible_paths = [
                # Path relative to ai_core.py
                os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "../../docs/TEAM_PERSONALITIES.md")
                ),
                # Path relative to project root (from ENV)
                os.path.join(
                    os.environ.get("PROJECT_ROOT", os.getcwd()), "docs/TEAM_PERSONALITIES.md"
                ),
                # Path relative to workspace root (if running from root)
                os.path.abspath("docs/TEAM_PERSONALITIES.md"),
                # Path relative to knowledge_os (if running from knowledge_os)
                os.path.abspath("../docs/TEAM_PERSONALITIES.md"),
                # Path relative to knowledge_os/app (if running from there)
                os.path.abspath("../../docs/TEAM_PERSONALITIES.md"),
                # Path relative to current working directory
                os.path.join(os.getcwd(), "docs/TEAM_PERSONALITIES.md"),
                os.path.join(os.getcwd(), "../docs/TEAM_PERSONALITIES.md"),
            ]

            personalities_path = None
            for p in possible_paths:
                if os.path.exists(p):
                    personalities_path = p
                    break

            if not personalities_path:
                # One last attempt: search for docs/TEAM_PERSONALITIES.md in parent directories
                curr = os.path.abspath(os.path.dirname(__file__))
                for _ in range(5):
                    p = os.path.join(curr, "docs/TEAM_PERSONALITIES.md")
                    if os.path.exists(p):
                        personalities_path = p
                        break
                    curr = os.path.dirname(curr)

            if not personalities_path:
                logger.warning("⚠️ [TEAM ENGINE] Personalities file not found. Using empty cache.")
                return

            with open(personalities_path, encoding="utf-8") as f:
                content = f.read()

            # Simple parsing: split by "### " and extract name + style
            sections = content.split("### ")[1:]
            for section in sections:
                lines = section.split("\n")
                if not lines:
                    continue
                header = lines[0].strip()
                # Extract name (e.g. "Igor" from "2. Igor (Backend Developer) - ...")
                name_part = header
                if ". " in header:
                    name_part = header.split(". ", 1)[1]
                if " (" in name_part:
                    name_part = name_part.split(" (", 1)[0]

                # Extract style (everything until the next "---" or end of section)
                style_content = "\n".join(lines[1:]).split("---")[0].strip()
                if name_part and style_content:
                    self._expert_styles_cache[name_part] = style_content
                    # Add English mapping for common experts
                    eng_mapping = {
                        "Виктория": "Victoria",
                        "Игорь": "Igor",
                        "Сергей": "Sergey",
                        "Анна": "Anna",
                        "Максим": "Maxim",
                        "Елена": "Elena",
                        "Дмитрий": "Dmitry",
                        "Роман": "Roman",
                        "Татьяна": "Tatiana",
                    }
                    if name_part in eng_mapping:
                        self._expert_styles_cache[eng_mapping[name_part]] = style_content

            self._last_cache_time = time.time()
            # logger.info(f"🧠 [TEAM ENGINE] Refreshed styles cache for {len(self._expert_styles_cache)} experts from {personalities_path}.")
        except Exception as e:
            logger.error(f"❌ [TEAM ENGINE] Error refreshing styles cache: {e}")

    async def generate_discussion(
        self,
        task_title: str,
        task_description: str,
        experts: List[str],
        context_data: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generates a multi-expert discussion for a given task.
        [SINGULARITY 26.1] Integrated AgentScope MsgHub for shared context.
        """
        logger.info(f"🧠 [TEAM ENGINE] Generating discussion for: {task_title}")

        # [AGENT SCOPE] MsgHub Integration
        try:
            import agentscope
            from agentscope.agents import DialogAgent, UserAgent
            from agentscope.msghub import MsgHub

            # Инициализация AgentScope если еще не сделано
            agentscope.init(
                model_configs=[
                    {
                        "config_name": "victoria_mlx",
                        "model_type": "openai_chat",
                        "api_key": "empty",
                        "base_url": "http://host.docker.internal:11435/v1",
                    }
                ]
            )

            # Создаем агентов для обсуждения
            expert_agents = []
            for name in experts:
                style = self._expert_styles_cache.get(name, "Professional expert.")
                expert_agents.append(
                    DialogAgent(
                        name=name,
                        sys_prompt=f"ТЫ - {name}. {style} Внедряй фазу 'Радикальной правды': критикуй неоптимальные идеи.",
                        model_config_name="victoria_mlx",
                    )
                )

            # Запускаем MsgHub
            with MsgHub(participants=expert_agents) as hub:
                # Начальное сообщение от Виктории (Team Lead)
                intro = f"Команда, задача: {task_title}. Описание: {task_description}. Контекст: {context_data[:500] if context_data else 'N/A'}"
                hub.broadcast({"role": "user", "content": intro})

                # Симулируем 2 круга обсуждения (мировые практики: дебаты повышают качество)
                for _ in range(2):
                    for agent in expert_agents:
                        agent.reply()

                # Собираем историю обсуждения
                discussion_history = hub.get_transcript()
                return discussion_history

        except Exception as e:
            logger.warning(f"⚠️ [AGENT SCOPE] MsgHub failed, falling back to legacy discussion: {e}")
            # Legacy fallback code...
            expert_styles = self._get_expert_styles(experts)

            prompt = f"""### ROLE: AI Director & Team Orchestrator
### TASK: Simulate a technical discussion between the following experts to solve the task.

### TASK TITLE: {task_title}
### TASK DESCRIPTION:
{task_description}

### EXPERTS INVOLVED:
{", ".join(experts)}

### EXPERT PERSONALITIES & STYLES:
{expert_styles}

### CONTEXT / CODE / DATA:
{context_data if context_data else "No additional context provided."}

### INSTRUCTIONS FOR THE MODEL:
1. Act as a Director coordinating a live dialogue between the experts.
2. Each expert MUST maintain their unique voice, catchphrases, and technical focus as described in their style.
3. The discussion should be highly technical, focused on solving the task, and identifying edge cases.
4. Experts should interact with each other (ask questions, confirm findings, suggest improvements).
5. Format the output in Markdown. Use **Expert Name:** for each turn.
6. Start with a brief intro by Victoria (Team Lead) and end with a summary/next steps by Victoria.
7. Keep the dialogue concise but meaningful.

### DISCUSSION:
"""
        if not self.router:
            self.router = _get_local_router()

        # Target MLX (port 11435) via specific category/flag
        result = await self.router.run_local_llm(
            prompt,
            category="team_discussion",
            is_vip=True,  # Team discussions are high priority
            expert_name="Виктория",
        )

        if isinstance(result, tuple):
            return result[0] or "⚠️ Failed to generate team discussion locally."
        return result or "⚠️ Failed to generate team discussion locally."


class FactExtractor:
    """
    [SINGULARITY 14.2] Fact Extraction Layer (MapReduce Pattern).
    Extracts key facts from long texts to prevent context overflow.
    """

    def __init__(self, model_name: str = "phi3.5:3.8b"):
        self.model_name = model_name
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        if (
            os.path.exists("/.dockerenv")
            or os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
        ):
            self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

    async def extract_facts(self, text: str, context_description: str = "general") -> str:
        """Extracts structured facts from text using a fast model."""
        if not text or len(text) < 100:
            return text

        import httpx

        prompt = f"""### ROLE: AI Secretary / Fact Extractor
### TASK: Extract key facts, metrics, and findings from the text below.
### CONTEXT: {context_description}
### FORMAT: Bullet points, concise, no fluff.

TEXT TO ANALYZE:
{text[:10000]}

FACTS:"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.1},
                    },
                )
                if response.status_code == 200:
                    return response.json().get("response", text)
        except Exception as e:
            logging.getLogger(__name__).warning(f"⚠️ [FactExtractor] Error: {e}")

        return text


try:
    from ui_audit_agent import get_ui_audit_agent
except ImportError:
    get_ui_audit_agent = None

try:
    from expert_hiring_manager import get_expert_hiring_manager
except ImportError:
    get_expert_hiring_manager = None

try:
    from hierarchical_memory import get_hierarchical_memory_manager
except ImportError:
    get_hierarchical_memory_manager = None

logger = logging.getLogger(__name__)

# Throttle TOOL CREATOR log (same message every 30s max at INFO to reduce noise)
_last_tool_creator_log_time = [0.0]

# Retry config for transient LLM failures (503, timeout, connection)
# При CB OPEN (recovery_timeout=120s) короткие 2/5/10s бесполезны —
# добавляем более длинный финальный retry (30s) для случаев когда CB начинает восстанавливаться
RETRY_BACKOFF_DELAYS = (5, 15, 30)  # seconds (увеличены: 2/5/10 → 5/15/30)
RETRY_MAX_ATTEMPTS = 1  # Reduced to prevent recursion

# Global user identification for conditional logic
USER_NAME = getpass.getuser()

_LOCAL_ROUTER_SINGLETON = None
_REDIS_MANAGER_SINGLETON = None
_SAFETY_CHECKER_SINGLETON = None
_DISTILLER_SINGLETON = None


def _get_local_router():
    """DI-style provider for a process-local LocalAIRouter instance."""
    global _LOCAL_ROUTER_SINGLETON
    # Recreate singleton if LocalAIRouter implementation changed (e.g. patched in tests).
    if LocalAIRouter and (
        _LOCAL_ROUTER_SINGLETON is None or _LOCAL_ROUTER_SINGLETON.__class__ is not LocalAIRouter
    ):
        _LOCAL_ROUTER_SINGLETON = LocalAIRouter()
    return _LOCAL_ROUTER_SINGLETON


def _get_redis_manager():
    """DI-style provider for RedisManager to avoid per-call re-instantiation."""
    global _REDIS_MANAGER_SINGLETON
    if _REDIS_MANAGER_SINGLETON is None and RedisManager:
        _REDIS_MANAGER_SINGLETON = RedisManager()
    return _REDIS_MANAGER_SINGLETON


def _get_safety_checker():
    """DI-style provider for SafetyChecker singleton."""
    global _SAFETY_CHECKER_SINGLETON
    if _SAFETY_CHECKER_SINGLETON is None and SafetyChecker:
        _SAFETY_CHECKER_SINGLETON = SafetyChecker()
    return _SAFETY_CHECKER_SINGLETON


def _get_distiller():
    """DI-style provider for KnowledgeDistiller singleton."""
    global _DISTILLER_SINGLETON
    if _DISTILLER_SINGLETON is None and KnowledgeDistiller:
        _DISTILLER_SINGLETON = KnowledgeDistiller()
    return _DISTILLER_SINGLETON


def _is_transient_llm_error(e_or_msg) -> bool:
    """Check if error/message indicates transient LLM failure (503, timeout, all-sources-unavailable)."""
    if e_or_msg is None:
        return False
    s = str(e_or_msg).lower()
    return (
        "503" in s
        or "queue is full" in s
        or "timeout" in s
        or "connection" in s
        or "unavailable" in s
        or "все источники недоступны" in s  # заглушка из _run_cloud_agent_async — тоже transient
        or "circuit breaker" in s
        or "maximum pending requests" in s
    )


async def _retry_llm_with_backoff(coro):
    """
    Retry async LLM call with exponential backoff on 503, timeout, connection errors.
    Fallback order: MLX -> Ollama -> cloud (documented in plan).
    """
    last_result = None
    for attempt in range(RETRY_MAX_ATTEMPTS):
        try:
            result = await coro()
            last_result = result
            if result is None:
                if attempt < RETRY_MAX_ATTEMPTS - 1:
                    delay = RETRY_BACKOFF_DELAYS[min(attempt, len(RETRY_BACKOFF_DELAYS) - 1)]
                    logger.info(
                        "Retry LLM in %s s (attempt %s/%s): got None",
                        delay,
                        attempt + 1,
                        RETRY_MAX_ATTEMPTS,
                    )
                    await asyncio.sleep(delay)
                    continue
                return result
            if isinstance(result, str) and _is_transient_llm_error(result):
                if attempt < RETRY_MAX_ATTEMPTS - 1:
                    delay = RETRY_BACKOFF_DELAYS[min(attempt, len(RETRY_BACKOFF_DELAYS) - 1)]
                    logger.info(
                        "Retry LLM in %s s (attempt %s/%s): %s",
                        delay,
                        attempt + 1,
                        RETRY_MAX_ATTEMPTS,
                        result[:80],
                    )
                    await asyncio.sleep(delay)
                    continue
            return result
        except (asyncio.TimeoutError, ConnectionError, OSError) as e:
            last_result = str(e)
        except Exception as e:
            if _is_transient_llm_error(str(e)) and attempt < RETRY_MAX_ATTEMPTS - 1:
                last_result = str(e)
            else:
                raise
        if attempt < RETRY_MAX_ATTEMPTS - 1:
            delay = RETRY_BACKOFF_DELAYS[min(attempt, len(RETRY_BACKOFF_DELAYS) - 1)]
            logger.info(
                "Retry LLM in %s s (attempt %s/%s) after %s",
                delay,
                attempt + 1,
                RETRY_MAX_ATTEMPTS,
                last_result[:80] if last_result else "error",
            )
            await asyncio.sleep(delay)
    return last_result


# --- PERFORMANCE BOOST: DB CONNECTION POOLING ---
_DB_POOL = None


async def _get_db_pool():
    """Lazy initialization of the PostgreSQL connection pool."""
    global _DB_POOL
    if _DB_POOL is None and asyncpg:
        try:
            default_url = (
                os.getenv("DATABASE_URL")
                or "postgresql://admin:secret@localhost:6432/knowledge_os?application_name=victoria_core"
            )
            db_url = os.getenv("DATABASE_URL_LOCAL", default_url)
            _DB_POOL = await asyncpg.create_pool(
                db_url,
                min_size=1,
                max_size=20,  # Увеличено для Singularity 24.1 (max_connections=500)
                max_inactive_connection_lifetime=300,
            )
        except Exception as exc:
            logger.error("❌ Failed to create DB pool: %s", exc)
    return _DB_POOL


async def _run_cloud_agent_async(
    prompt: str,
    category: Optional[str] = "general",
    is_vip: bool = False,
    expert_name: str = "Виктория",
):
    """
    [SINGULARITY 28.6] Smart Cloud Fallback.
    Priority: Local (MLX/Ollama) -> OpenRouter (Free/Paid) -> cursor-agent -> Local Lighter Models.
    """
    # ПРИОРИТЕТ 1: локальные модели (Ollama/MLX) — политика корпорации
    # Health check перед запросом (2.3 плана): пропускаем заведомо недоступные узлы
    use_local = bool(LocalAIRouter)
    if use_local:
        try:
            _router = _get_local_router()
            healthy = await _router.check_health(force_refresh=False)
            if not healthy:
                logger.info("[HEALTH CHECK] No healthy local nodes, skipping to cloud/cursor-agent")
                use_local = False
        except Exception as hc_err:
            logger.debug("[HEALTH CHECK] Error: %s, will try local anyway", hc_err)
    if use_local and LocalAIRouter:

        async def _try_local():
            router = _get_local_router()
            result = await router.run_local_llm(
                prompt, category=category, is_vip=is_vip, expert_name=expert_name
            )
            if isinstance(result, tuple):
                response, _ = result
            else:
                response = result
            return response

        try:
            response = await _retry_llm_with_backoff(_try_local)
            if response and len(str(response)) > 10:
                logger.info(
                    "✅ [LOCAL FIRST] Использована локальная модель (Ollama/MLX) вместо облака"
                )
                return response
        except Exception as e:
            logger.warning("⚠️ [LOCAL FIRST] Локальный роутер недоступен: %s", e)
            # В STRICT_LOCAL режиме не переходим на cursor-agent
            if is_strict_local():
                logger.error(
                    "[STRICT_LOCAL] Локальные модели недоступны, cursor-agent заблокирован"
                )
                logger.info("[GRACEFUL DEGRADATION] Попытка повторного вызова локальных моделей...")
                # Ещё одна попытка retry с backoff (уже есть в _try_local, но это последний шанс)
                try:
                    response = await _retry_llm_with_backoff(_try_local)
                    if response and len(str(response)) > 10:
                        logger.info("[STRICT_LOCAL] ✅ Повторный вызов локальных моделей успешен")
                        return response
                except Exception as retry_err:
                    logger.error(f"[STRICT_LOCAL] ❌ Повторный вызов также неудачен: {retry_err}")

                # Локальные модели недоступны даже после retry — возвращаем явную ошибку
                return (
                    "⚠️ Локальные модели недоступны (STRICT_LOCAL). "
                    "Проверьте MLX (11435), Ollama (11434) и Recovery Listener (9099). "
                    "Для восстановления выполните: curl -s -X POST http://localhost:9099/recover"
                )

    # ПРИОРИТЕТ 2: OpenRouter — реальный облачный fallback только при наличии ключа.
    # [SINGULARITY 28.7] Pre-emptive Backpressure: Failover to OpenRouter if Ollama is overloaded.
    try:
        rm = _get_redis_manager()
        if rm is None:
            raise RuntimeError("RedisManager unavailable for backpressure check")
        client = await rm.get_client()
        slots_val = await client.get("ollama:global_slots")
        if slots_val and int(slots_val) >= int(os.getenv("OLLAMA_GLOBAL_MAX_SLOTS", "2")):
            logger.info(
                "⏩ [BACKPRESSURE] Ollama global slots full, pre-emptive failover to OpenRouter"
            )
            # If we are here, it means we skip Priority 1 (Local) or it failed/overloaded
    except Exception as bp_err:
        logger.debug(f"Backpressure check failed in ai_core: {bp_err}")

    # Пустые OPENAI/ANTHROPIC/DEEPSEEK ключи намеренно не считаются рабочим fallback.
    openrouter_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if openrouter_key and not is_strict_local():
        try:
            import httpx

            openrouter_model = os.getenv(
                "OPENROUTER_FALLBACK_MODEL",
                "mistralai/mistral-7b-instruct:free",
            )
            if category == "coding":
                openrouter_model = os.getenv(
                    "OPENROUTER_CODING_MODEL",
                    "qwen/qwen-2.5-coder-32b-instruct:free",
                )

            logger.info("☁️ [OPENROUTER] Пробуем облачный fallback: %s", openrouter_model)
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {openrouter_key}",
                        "HTTP-Referer": os.getenv(
                            "OPENROUTER_HTTP_REFERER",
                            "https://github.com/atra-web-ide",
                        ),
                        "X-Title": os.getenv("OPENROUTER_APP_TITLE", "ATRA Web IDE"),
                    },
                    json={
                        "model": openrouter_model,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
            if resp.status_code == 200:
                data = resp.json()
                response = data.get("choices", [{}])[0].get("message", {}).get("content")
                if response and len(response) > 10:
                    logger.info("✅ [OPENROUTER] Ответ получен")
                    return response
            logger.warning("⚠️ [OPENROUTER] Ошибка API: %s %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.warning("⚠️ [OPENROUTER] Недоступен: %s", e)
    else:
        logger.info("☁️ [OPENROUTER] Пропущен: OPENROUTER_API_KEY не задан")

    # ПРИОРИТЕТ 3: cursor-agent (облако) — только если локальные модели недоступны
    # В STRICT_LOCAL режиме cursor-agent заблокирован
    if is_strict_local():
        logger.warning("[STRICT_LOCAL] cursor-agent заблокирован, возвращаем ошибку")
        return (
            "⚠️ Локальные модели недоступны (STRICT_LOCAL). "
            "cursor-agent заблокирован. Проверьте MLX (11435), Ollama (11434) и Recovery (9099): "
            "curl -X POST http://localhost:9099/recover или отключите STRICT_LOCAL."
        )

    try:
        env = os.environ.copy()
        agent_path = "cursor-agent"
        process = await asyncio.create_subprocess_exec(
            agent_path,
            "--print",
            prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            # Уменьшаем таймаут до 30 секунд для быстрого fallback
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            if process.returncode == 0:
                return stdout.decode().strip()
            return f"⚠️ Ошибка облачного мозга: {stderr.decode()[:100]}"
        except asyncio.TimeoutError:
            process.kill()
            logger.warning(
                "⏱️ [CLOUD TIMEOUT] Облачный запрос таймаутился (30s), переключаюсь на локальные модели"
            )
            # При таймауте облака пытаемся использовать локальные модели
            if LocalAIRouter:
                try:
                    router = _get_local_router()
                    # Быстрый fallback на локальные модели с таймаутом 15 секунд
                    result = await asyncio.wait_for(
                        router.run_local_llm(
                            prompt, category=category, is_vip=is_vip, expert_name=expert_name
                        ),
                        timeout=15,
                    )
                    if isinstance(result, tuple):
                        response, _ = result
                    else:
                        response = result
                    if response and len(response) > 10:
                        logger.info(
                            "✅ [TIMEOUT FALLBACK] Использованы локальные модели после таймаута облака"
                        )
                        return response
                except asyncio.TimeoutError:
                    logger.warning("⚠️ [TIMEOUT FALLBACK] Локальные модели также таймаутятся (15s)")
                except Exception as e:
                    logger.warning(f"⚠️ [TIMEOUT FALLBACK] Локальные модели также недоступны: {e}")
            return (
                "⌛ Облачный запрос занял слишком много времени. Локальные модели также недоступны."
            )
    except FileNotFoundError:
        # [SINGULARITY 23.2] Inference Optimizer: Pre-loading next model
        try:
            from app.inference_optimizer import get_inference_optimizer

            optimizer = get_inference_optimizer()
            asyncio.create_task(optimizer.predict_and_preload(category))
        except Exception as e:
            logger.debug(f"Inference Optimizer failed: {e}")

        # 🍎 ПРИОРИТЕТ 1: Попробовать MLX (Apple Neural Engine) на Mac Studio
        try:
            from knowledge_os.app.mlx_router import get_mlx_router, is_mlx_available

            if is_mlx_available():
                mlx_router = get_mlx_router()
                mlx_response = await mlx_router.generate_response(
                    prompt=prompt, max_tokens=512, temperature=0.7
                )
                if mlx_response and len(mlx_response) > 10:
                    logger.info("✅ [MLX] Использован Apple MLX")
                    return mlx_response
        except Exception as e:
            logger.debug(f"⚠️ [MLX] Ошибка: {e}")

        # ПРИОРИТЕТ 2: cursor-agent not found - use direct Ollama call as fallback
        _in_docker = (
            os.path.exists("/.dockerenv")
            or os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
        )
        if _in_docker:
            logger.debug("⚠️ cursor-agent not found (expected in Docker), using direct Ollama API")
        else:
            logger.warning("⚠️ cursor-agent not found, using direct Ollama API")
        try:
            import aiohttp

            # Таймаут запроса к Ollama: по умолчанию 600 с (Сингулярность 10.0: увеличено для тяжелых моделей)
            _ollama_timeout = float(
                os.getenv("LOCAL_ROUTER_LLM_TIMEOUT", os.getenv("SMART_WORKER_LLM_TIMEOUT", "600"))
            )
            if (
                "Совет" in prompt
                or "стратег" in prompt
                or "анализ" in prompt
                or "coding" in str(category)
                or "reasoning" in str(category)
            ):
                _ollama_timeout = max(_ollama_timeout, 1800.0)
                logger.info(
                    f"🕒 [AI_CORE] Увеличен таймаут Ollama до {_ollama_timeout}с для тяжелой задачи"
                )
            # В Docker localhost недоступен — используем OLLAMA_BASE_URL/host.docker.internal
            _ollama_base = (
                os.getenv("OLLAMA_BASE_URL")
                or os.getenv("OLLAMA_API_URL")
                or os.getenv("SERVER_LLM_URL")
            )
            if not _ollama_base:
                _is_docker = (
                    os.path.exists("/.dockerenv")
                    or os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
                )
                _ollama_base = (
                    "http://host.docker.internal:11434" if _is_docker else "http://localhost:11434"
                )
            ollama_urls = [_ollama_base]
            # keep_alive: используем централизованную политику (MODEL_UNLOADING_AND_MEMORY)
            # В ai_core fallback вызывается когда MLX недоступен
            async with aiohttp.ClientSession() as session:
                # Mac Studio: используем локальные модели (Ollama и MLX)
                for ollama_url in ollama_urls:
                    try:
                        # Mac Studio: доступны лучшие модели
                        # Локальные модели (70b удалены)
                        # Ollama модели: glm-4.7-flash:q8_0, phi3.5:3.8b
                        if (
                            "localhost" in ollama_url
                            or "127.0.0.1" in ollama_url
                            or "host.docker.internal" in ollama_url
                        ):
                            # Mac Studio - лучшие модели (victoria-wisdom приоритет)
                            models_to_try = [
                                "victoria-wisdom-v3.5:latest",
                                "phi3.5:3.8b",
                                "qwen3.5:35b",
                                "tinyllama:1.1b-chat",
                            ]
                        else:
                            # Внешний сервер - легкие модели (если потребуется)
                            models_to_try = [
                                "phi3:latest",
                                "phi3",
                                "phi4:latest",
                                "phi4",
                                "tinyllama",
                                "gemma:2b",
                            ]

                        response = None
                        model_used = None

                        for model_name in models_to_try:
                            try:
                                _keep_alive = get_keep_alive(model_name, mlx_alive=False)
                                async with session.post(
                                    f"{ollama_url}/api/generate",
                                    json={
                                        "model": model_name,
                                        "prompt": prompt,
                                        "stream": False,
                                        "keep_alive": _keep_alive,
                                    },
                                    timeout=aiohttp.ClientTimeout(total=_ollama_timeout),
                                ) as resp:
                                    if resp.status == 200:
                                        data = await resp.json()
                                        response = data.get("response", "")
                                        if response and len(response) > 10:
                                            model_used = model_name
                                            break
                            except Exception as e:
                                logger.debug(f"Model {model_name} at {ollama_url} failed: {e}")
                                continue

                        if response and model_used:
                            logger.info(
                                f"✅ [FALLBACK] Used Ollama at {ollama_url} with {model_used}"
                            )
                            return response
                        else:
                            logger.debug("No Ollama fallback model succeeded at %s", ollama_url)
                    except Exception as e:
                        logger.debug(f"Ollama at {ollama_url} failed: {e}")
                        continue
        except ImportError:
            logger.warning("aiohttp not available for Ollama fallback")
        except Exception as e:
            logger.warning(f"Ollama fallback failed: {e}")

        # Final fallback: smart_worker распознаёт "недоступн" и вызывает rule_executor
        return "[SYSTEM: All LLM sources unavailable]"
    except Exception as exc:
        return "[SYSTEM: Cloud connection error]"


async def _safe_cloud_response(response: str) -> str:
    """[SINGULARITY 31.3] Apply SafetyChecker to cloud responses."""
    if not response or response.startswith("[SYSTEM:"):
        return response
    try:
        from app.safety_checker import get_safety_checker

        checker = get_safety_checker()
        is_safe, score, warnings = checker.check_response(response)
        if not is_safe:
            logger.warning(f"🛡️ [SAFETY] Cloud response blocked (score={score:.2f}): {warnings[:2]}")
            return "[SYSTEM: Response blocked by safety checker]"
    except Exception:
        pass
    return response


async def _enrich_with_deep_memory(nodes: list, pool) -> str:
    """
    Extract unique domain_ids from nodes and fetch domain summaries (Deep Memory).
    """
    if not nodes or not pool:
        return ""

    domain_ids = set()
    for node in nodes:
        # Vector RAG rows are asyncpg.Record or dict
        if hasattr(node, "get"):
            did = node.get("domain_id")
        else:
            # Fallback for other node structures if any
            did = getattr(node, "domain_id", None)

        if did:
            domain_ids.add(did)

    if not domain_ids:
        return ""

    try:
        async with pool.acquire() as conn:
            # Fetch domain summaries and domain names
            rows = await conn.fetch(
                """
                SELECT d.name as domain_name, kn.content
                FROM knowledge_nodes kn
                JOIN domains d ON kn.domain_id = d.id
                WHERE kn.domain_id = ANY($1::uuid[])
                  AND kn.metadata->>'type' = 'domain_summary'
                """,
                list(domain_ids),
            )

            if not rows:
                return ""

            enrichment = "\n<deep_memory>\n"
            for row in rows:
                enrichment += f'  <domain name="{row["domain_name"]}">\n'
                enrichment += f"    {row['content']}\n"
                enrichment += "  </domain>\n"
            enrichment += "</deep_memory>\n"
            return enrichment
    except Exception as e:
        logger.error(f"Deep Memory enrichment failed: {e}")
        return ""


async def _get_knowledge_context(query: str, project_context: Optional[str] = None) -> str:
    """Retrieve relevant knowledge nodes (GraphRAG). If project_context set, project_files filtered by project."""
    return await _get_knowledge_context_impl(query, project_context)


@profile_function("ai_core")
async def _get_knowledge_context_impl(query: str, project_context: Optional[str] = None) -> str:
    """Implementation of knowledge retrieval. project_context scopes project_files RAG to that project."""
    if get_traffic_mirror:
        tm = get_traffic_mirror()
        await tm.mirror_request("ai_core", "_get_knowledge_context", query)

    try:
        # [SINGULARITY 21.22] Parallel RAG Execution: GraphRAG + VectorRAG
        async def fetch_graph():
            try:
                from app.graphrag.graphrag_service import get_graphrag_service

                graphrag = get_graphrag_service()
                graph_context, graph_nodes = await graphrag.retrieve_graph_context(query)

                # [SINGULARITY 21.25] Deep Memory Hierarchical Enrichment for GraphRAG
                if graph_nodes:
                    pool = await _get_db_pool()
                    deep_memory = await _enrich_with_deep_memory(graph_nodes, pool)
                    if deep_memory:
                        graph_context = deep_memory + graph_context

                return graph_context
            except Exception as ge:
                logger.debug(f"GraphRAG failed: {ge}")
                return None

        async def fetch_visual(refined_query: Optional[str] = None):
            """[OMNI-RAG v3] Coarse-to-Fine Visual Context Retrieval."""
            search_query = refined_query or query
            try:
                if not LocalAIRouter:
                    return ""
                router = _get_local_router()
                visual_results = await router.search_visual_context(search_query)
                if not visual_results:
                    return ""

                context = "\n🖼️ [VISUAL CONTEXT (OMNI-RAG v3)]:\n"
                for res in visual_results:
                    context += f"\n[IMAGE/PDF: {res.get('file_path')}] (similarity: {res.get('similarity', 0):.2f}):\n"
                    context += f"Description: {res.get('description', 'N/A')}\n"
                return context
            except Exception as e:
                logger.debug(f"VisualRAG failed: {e}")
                return ""

        async def fetch_vector():
            try:
                # [SINGULARITY 31.0] Quantum Leap: LanceDB Zero-Latency RAG
                try:
                    from app.lancedb_service import get_lancedb_service

                    lancedb_svc = get_lancedb_service()

                    embedding = await get_embedding(query)
                    if embedding:
                        lancedb_results = await lancedb_svc.search(embedding, limit=5)
                        if lancedb_results:
                            logger.info("⚡ [LANCEDB RAG] Zero-latency context retrieved.")
                            context = "\n⚡ [KNOWLEDGE CONTEXT (LANCEDB-ACCELERATED)]:\n"
                            for r in lancedb_results:
                                if r["similarity"] >= 0.6:  # Higher threshold for vector search
                                    file_path = r["metadata"].get("file_path", "N/A")
                                    context += f"\n[NODE: {file_path}] (релевантность: {r['similarity']:.2f}):\n"
                                    context += f"{r['content'][:1200]}\n"

                            if "[LANCEDB-ACCELERATED]" in context:
                                return context
                except Exception as le:
                    logger.debug(f"LanceDB RAG failed, falling back: {le}")

                # [AGENT SCOPE] ReMe Memory Integration (optional — falls through if not available)
                try:
                    from agentscope.memory import ReMe

                    reme = ReMe(config={"type": "hybrid", "top_k": 5})
                    reme_context = reme.retrieve(query)
                    if reme_context:
                        logger.info("🧠 [AGENT SCOPE] ReMe context retrieved.")
                        return f"\n🧠 [WORKING MEMORY (ReMe)]:\n{reme_context}\n"
                except (ImportError, Exception) as _reme_err:
                    logger.debug(f"ReMe not available, using VectorRAG: {_reme_err}")

                embedding = await get_embedding(query)
                if not embedding:
                    return ""

                # [SINGULARITY 21.23] Try Rust RAG first
                try:
                    import httpx

                    # Gateway is HTTP in local Docker profile unless mTLS is explicitly configured.
                    rust_url = os.getenv(
                        "RUST_GATEWAY_URL",
                        "http://atra-web-ide-gateway:8081/api/knowledge/search_v2",
                    )
                    # [SINGULARITY 29.6] Context Limit Adaptation for R&D
                    # R&D tasks often have huge context, we limit nodes to prevent memory overflow
                    is_rd_query = "#rd" in query.lower() or (
                        project_context and "#rd" in project_context.lower()
                    )
                    limit_nodes = 5 if is_rd_query else 10

                    payload = {
                        "embedding": embedding,
                        "project_context": project_context,
                        "limit": limit_nodes,  # Adaptive limit
                        "use_quantum": not is_rd_query,  # Disable quantum for R&D to save RAM
                    }

                    # mTLS сертификаты для клиента (Singularity 21.24)
                    cert_path = os.getenv("BRIDGE_CERT_PATH")
                    key_path = os.getenv("BRIDGE_KEY_PATH")
                    ca_path = os.getenv("BRIDGE_CA_PATH")

                    client_kwargs = {"timeout": 10.0}
                    if cert_path and key_path:
                        import ssl

                        ssl_ctx = ssl.create_default_context(cafile=ca_path)
                        ssl_ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
                        client_kwargs["verify"] = ssl_ctx
                    else:
                        client_kwargs["verify"] = False  # Insecure fallback

                    async with httpx.AsyncClient(**client_kwargs) as client:
                        try:
                            response = await client.post(rust_url, json=payload)
                        except Exception as first_err:
                            err_txt = str(first_err)
                            if "WRONG_VERSION_NUMBER" in err_txt and rust_url.startswith(
                                "https://"
                            ):
                                # Compatibility retry for mixed HTTP/TLS deployments.
                                fallback_url = "http://" + rust_url[len("https://") :]
                                logger.info("🔁 [RUST RAG] TLS mismatch, retrying over HTTP.")
                                response = await client.post(fallback_url, json=payload)
                            else:
                                raise
                        if response.status_code == 200:
                            nodes = response.json()
                            if not nodes:
                                # [FIX v31.2] Если Rust RAG пуст, не падаем в Exception, а идем дальше к Python RAG
                                logger.info(
                                    "📭 [RUST RAG] No nodes found, falling back to Python RAG."
                                )
                                raise StopIteration("Empty Rust RAG")

                            context = "\n📚 [KNOWLEDGE CONTEXT (RUST-ACCELERATED)]:\n"
                            for node in nodes:
                                # (node.get("similarity") or 0) — защита от similarity=null в JSON
                                sim = node.get("similarity") or 0
                                if sim >= 0.55:
                                    meta = node.get("metadata") or {}
                                    file_path = meta.get("file_path", "N/A")
                                    context += (
                                        f"\n[NODE: {file_path}] (релевантность: {sim:.2f}):\n"
                                    )
                                    context += f"{node['content'][:1200]}\n"
                            logger.info("🚀 [RUST RAG] Successfully retrieved context.")

                            # [SINGULARITY 21.25] Deep Memory Hierarchical Enrichment
                            pool = await _get_db_pool()
                            deep_memory = await _enrich_with_deep_memory(nodes, pool)
                            if deep_memory:
                                context = deep_memory + context

                            return context
                except StopIteration:
                    # Специальный случай для пустого ответа Rust RAG
                    pass
                except Exception as re:
                    # [FIX v31.4] Move to INFO level entirely. Falling back to Python is a normal operational path.
                    # We only log the actual error string if it exists to keep logs clean.
                    err_msg = str(re).strip()
                    if err_msg:
                        logger.info(f"📡 Rust RAG fallback: {err_msg}")
                    else:
                        logger.info("📡 Rust RAG empty or unavailable, using Python fallback.")

                # Fallback to Python RAG (old logic)
                pool = await _get_db_pool()
                if not pool:
                    return ""

                # [SINGULARITY 21.22] In-memory domain cache
                from domain_cache import get_domain_id

                async with pool.acquire() as conn:
                    ai_research_id = await get_domain_id(conn, "AI Research")
                    victoria_tasks_id = await get_domain_id(conn, "victoria_tasks")
                    project_files_id = await get_domain_id(conn, "project_files")

                    pc = (project_context or "").strip()
                    params = [str(embedding)]

                    if pc:
                        project_cond = """
                            AND (
                                domain_id = $2
                                OR domain_id = $3
                                OR metadata->>'source' = 'external_docs_indexer'
                                OR source_ref = 'autonomous_worker'
                                OR ( (domain_id = $4 OR metadata->>'source' = 'indexing_daemon')
                                     AND (metadata->>'project_slug' = $5 OR metadata->>'file_path' LIKE '%' || $5 || '%') )
                            )
                        """
                        params.extend([ai_research_id, victoria_tasks_id, project_files_id, pc])
                    else:
                        project_cond = """
                            AND (
                                domain_id = $2
                                OR domain_id = $3
                                OR domain_id = $4
                                OR metadata->>'source' = 'external_docs_indexer'
                                OR metadata->>'source' = 'indexing_daemon'
                                OR source_ref = 'autonomous_worker'
                            )
                        """
                        params.extend([ai_research_id, victoria_tasks_id, project_files_id])

                    rows = await conn.fetch(
                        f"""
                        SELECT content, metadata, domain_id,
                               ((1 - (embedding <=> $1::vector)) * (CASE WHEN metadata->>'low_priority' = 'true' THEN 0.5 ELSE 1.0 END)) as similarity
                        FROM knowledge_nodes
                        WHERE embedding IS NOT NULL AND confidence_score >= 0.3
                        {project_cond}
                        ORDER BY similarity DESC LIMIT 8
                        """,
                        *params,
                    )

                    if not rows:
                        return ""

                    # [SINGULARITY 23.3] Cross-Encoder Reranking for Python RAG
                    try:
                        # [SINGULARITY 29.6] Skip reranking for R&D to save memory
                        if is_rd_query:
                            reranked_nodes = rows[:5]
                        elif os.getenv("RAG_RERANKER_ENABLED", "true").lower() in (
                            "false",
                            "0",
                            "no",
                        ):
                            reranked_nodes = rows[:5]
                        else:
                            from app.rag_reranker import get_rag_reranker

                            reranker = get_rag_reranker()
                            # Преобразуем Record в dict для reranker
                            nodes_to_rerank = [dict(row) for row in rows]
                            reranked_nodes = reranker.rerank(query, nodes_to_rerank, top_k=5)
                        rows = reranked_nodes  # Используем переранжированные узлы
                    except Exception as e:
                        logger.debug(f"Reranking failed: {e}")

                    # [SINGULARITY 21.25] Deep Memory Hierarchical Enrichment
                    deep_memory = await _enrich_with_deep_memory(rows, pool)

                    context = "\n📚 [KNOWLEDGE CONTEXT (AI Research & Corp)]:\n"
                    if deep_memory:
                        context = deep_memory + context
                    for row in rows:
                        if row["similarity"] >= 0.55:
                            meta = row["metadata"] or {}
                            if isinstance(meta, str):
                                try:
                                    meta = json.loads(meta)
                                except Exception:
                                    meta = {}

                            source = meta.get("source", "unknown")
                            file_path = meta.get("file_path", "N/A")

                            if source == "external_docs_indexer":
                                context += f"\n[AI RESEARCH: {file_path}] (релевантность: {row['similarity']:.2f}):\n"
                            elif source == "indexing_daemon":
                                context += f"\n[PROJECT FILE: {file_path}] (релевантность: {row['similarity']:.2f}):\n"
                            elif meta.get("type") == "corporate_system":
                                context += f"\n[КОРПОРАЦИЯ: СИСТЕМА] (релевантность: {row['similarity']:.2f}):\n"
                            else:
                                context += f"\n[ЗНАНИЕ] (релевантность: {row['similarity']:.2f}):\n"

                            context += f"{row['content'][:1200]}\n"
                    return context
            except Exception as ve:
                logger.error(f"Vector RAG failed: {ve}")
                return ""

        # [OMNI-RAG v3] Coarse-to-Fine Iterative Search
        # Step 1: Coarse search (Graph + Vector)
        graph_task = asyncio.create_task(fetch_graph())
        vector_task = asyncio.create_task(fetch_vector())
        graph_context, vector_context = await asyncio.gather(graph_task, vector_task)

        # Step 2: Fine search (Visual) if needed
        visual_context = ""
        prompt_lower = query.lower()
        is_multimodal = "#multimodal" in prompt_lower or any(
            kw in prompt_lower for kw in ["скриншот", "интерфейс", "схема", "ui", "дизайн"]
        )

        if is_multimodal:
            logger.info("🎨 [OMNI-RAG] Multimodal query detected, performing fine visual search...")
            visual_context = await fetch_visual()
        elif graph_context or vector_context:
            # Анализируем текстовый контекст: если там есть упоминания визуальных артефактов, делаем fine search
            combined_text = (graph_context or "") + (vector_context or "")
            if any(
                kw in combined_text.lower()
                for kw in ["image", "screenshot", "diagram", "pdf", "ui_design"]
            ):
                logger.info(
                    "🔍 [OMNI-RAG] Visual artifacts mentioned in text context, refining search..."
                )
                visual_context = await fetch_visual()

        if visual_context:
            logger.info("🖼️ [OMNI-RAG] Visual context retrieved. Verifying via ConsensusAgent...")
            try:
                # Упрощенная верификация: проверяем, не противоречит ли визуальный контекст текстовому
                verification_prompt = f"""
                Verify if the following visual context matches the textual context for the query: "{query}"
                TEXTUAL CONTEXT: {graph_context[:1000]}... {vector_context[:1000]}...
                VISUAL CONTEXT: {visual_context}
                Respond with 'VALID' or 'INVALID' and a brief reason.
                """
                # Используем легкую модель для верификации
                _vr = _get_local_router()
                if not _vr:
                    raise RuntimeError("LocalAIRouter unavailable for visual verification")
                v_res = await _vr.run_local_llm(verification_prompt, category="fast")
                if isinstance(v_res, tuple) and "INVALID" in str(v_res[0]):
                    logger.warning(f"⚠️ [OMNI-RAG] Visual context verification failed: {v_res[0]}")
                    visual_context = f"⚠️ [VERIFICATION FAILED]: {visual_context}"
                else:
                    logger.info("✅ [OMNI-RAG] Visual context verified.")
            except Exception as ce:
                logger.debug(f"Consensus verification failed: {ce}")

        full_context = ""
        if graph_context:
            logger.info("🌐 [GRAPHRAG] Context retrieved.")
            full_context += graph_context + "\n"
        if visual_context:
            logger.info("🖼️ [OMNI-RAG] Visual context retrieved.")
            full_context += visual_context + "\n"
        if vector_context:
            full_context += vector_context

        # [SINGULARITY 21.25] Global Deep Memory Hierarchical Enrichment (for GraphRAG)
        # Already handled inside fetch_graph for GraphRAG path and fetch_vector for VectorRAG path.
        return full_context

    except Exception as exc:
        logger.error(f"Knowledge retrieval error: {exc}")
        return ""


async def run_smart_agent_async(
    prompt: str,
    expert_name: str = "Виктория",
    category: Optional[str] = None,
    require_cot: bool = False,
    is_critical: bool = False,
    images: Optional[list] = None,
    session_id: Optional[str] = None,
    local_router=None,
    is_vip: bool = False,
    project_context: Optional[str] = None,
    symbols: Optional[List[str]] = None,
):
    """
    Hybrid Intelligence Orchestrator with Model Ensemble (Singularity 14.0).
    Victoria (Cloud) generates the plan, Local Worker (DeepSeek/Qwen) executes.
    project_context: scopes RAG and prompt to that project (e.g. setki-21).
    symbols: [SINGULARITY 28.X] Behavior symbols for Symbol Tuning (concise, creative, etc.)
    """
    # [SINGULARITY 28.X] Apply Symbol Tuning if provided
    if symbols:
        try:
            from symbol_tuner import get_symbol_tuner

            tuner = get_symbol_tuner()
            prompt = tuner.apply_symbols(prompt, symbols)
        except ImportError:
            pass

    # [SINGULARITY 31.3] Try v2 pipeline if enabled (feature flag)
    if os.getenv("USE_AI_PIPELINE_V2", "false").lower() in ("true", "1", "yes"):
        try:
            try:
                from app.ai_pipeline import run_smart_agent_async_v2
            except Exception:
                from ai_pipeline import run_smart_agent_async_v2
            return await run_smart_agent_async_v2(
                prompt,
                expert_name,
                category,
                require_cot,
                is_critical,
                images,
                session_id,
                local_router,
                is_vip,
                project_context,
            )
        except Exception as v2_err:
            logger.debug(f"[V2] Fallback to v1: {v2_err}")

    return await run_smart_agent_async_impl(
        prompt,
        expert_name,
        category,
        require_cot,
        is_critical,
        images,
        session_id,
        local_router,
        is_vip,
        project_context,
    )


@profile_function("ai_core")
async def run_smart_agent_async_impl(
    prompt: str,
    expert_name: str = "Виктория",
    category: Optional[str] = None,
    require_cot: bool = False,
    is_critical: bool = False,
    images: Optional[list] = None,
    session_id: Optional[str] = None,
    local_router=None,
    is_vip: bool = False,
    project_context: Optional[str] = None,
):
    start_time = time.time()

    # [SINGULARITY 31.3] Pipeline: memory crystals, threats, anti-hallucination
    try:
        from app.ai_pipeline import (
            check_threats,
            clean_response,
            inject_anti_hallucination,
            inject_context_enrichment,
            inject_expert_dna,
            inject_wisdom,
            load_memory_crystals,
            strip_think_blocks,
        )
    except Exception:
        from ai_pipeline import (
            check_threats,
            clean_response,
            inject_anti_hallucination,
            inject_context_enrichment,
            inject_expert_dna,
            inject_wisdom,
            load_memory_crystals,
            strip_think_blocks,
        )

    memory_crystals = await load_memory_crystals(project_context)

    # [SINGULARITY 26.9] Queue complex tasks to Redis worker
    goal_lower = (prompt or "").lower()
    # [SINGULARITY 10.3] Bypass queue for discussion mode
    # [SINGULARITY 10.5] Фикс: более надежный поиск тега (игнорируем регистр и пробелы)
    is_discussion_mode = "[system: team_discussion_mode]" in goal_lower

    # [SINGULARITY 10.8] Фикс: если это режим обсуждения, мы НЕ добавляем системные инструкции,
    # которые могут спровоцировать Swarm/Handoff или галлюцинации о ролях.
    if is_discussion_mode:
        # В режиме обсуждения мы доверяем промпту из прокси
        pass
    else:
        # [SINGULARITY 27.1] Load expert's system_prompt from DB
        expert_system_prompt = ""
        try:
            from expert_services import get_expert_system_prompt

            expert_system_prompt = get_expert_system_prompt(expert_name) or ""
            if expert_system_prompt:
                logger.info(f"🎭 [SYSTEM_PROMPT] Loaded for {expert_name}")
        except Exception as e:
            logger.debug(f"Failed to load system_prompt: {e}")

    # [SINGULARITY 21.32] Token Efficiency Audit
    prompt = audit_efficiency(prompt)

    # [SINGULARITY 27.1] Inject expert's system_prompt FIRST
    if not is_discussion_mode and expert_system_prompt:
        prompt = f"### ТЫ — {expert_name.upper()}\n{expert_system_prompt}\n\n{prompt}"

    # [SINGULARITY 31.3] Threat Detection — проверяем промпт
    is_threat, threat_types = check_threats(prompt)
    if is_threat:
        return _build_error_response(f"[SECURITY] Prompt rejected: {threat_types}")

    # [SINGULARITY 27.0] Anti-Hallucination Instruction
    prompt = inject_anti_hallucination(prompt, expert_name, is_discussion_mode)

    # [SINGULARITY 23.0] U-Shape Context Assembly (TOP)
    if memory_crystals:
        prompt = memory_crystals + "\n" + prompt
        logger.info(f"💎 [MEMORY CRYSTALS] Injected into TOP of context for {project_context}")

    # [SINGULARITY 21.33] Skeleton-of-Thought (SoT) Prototype
    if "создай" in prompt.lower() and "план" in prompt.lower():
        sot_instruction = """
        ### [SYSTEM: SKELETON-OF-THOUGHT ENABLED]
        1. Сначала выведи только структуру (скелет) ответа.
        2. Затем для каждого пункта скелета напиши детальное содержание.
        Это позволит ускорить генерацию и сделать ответ более структурированным.
        """
        prompt = sot_instruction + prompt

    # [SINGULARITY 21.0] Enforce CoT for critical tasks
    if not is_discussion_mode and (is_critical or category in ("reasoning", "vip")):
        require_cot = True
        if "ПОШАГОВО" not in prompt:
            prompt = f"### [SYSTEM: ENFORCED REASONING MODE]\nРЕШИ ЗАДАЧУ ПОШАГОВО (Chain-of-Thought).\n\n{prompt}"

    # [SINGULARITY 26.3] COLLECTIVE REFLECTION LOOP (Reasoning Trace)
    # Only inject for large models or reasoning/vip categories — small models (phi3.5 3.8B) ignore it.
    _is_large_model = (
        is_vip
        or category in ("reasoning", "vip")
        or any(x in str(expert_name).lower() for x in ("виктория", "victoria"))
    )
    reflection_instruction = """
### COLLECTIVE REFLECTION PROTOCOL:
Your answer MUST contain a hidden block <reasoning_trace> with:
1. Your doubts when choosing the solution.
2. Alternative approaches you rejected and why.
3. Your confidence score (0-100%).
This block will be analyzed by other agents for collective verification.
"""
    if not is_discussion_mode and _is_large_model:
        prompt = reflection_instruction + "\n" + prompt

    # [SINGULARITY 26.2] SWARM & HANDOFF INSTRUCTIONS
    # Only inject for Victoria (orchestrator role) — other experts should not initiate handoffs.
    swarm_instruction = """
### SWARM & HANDOFF PROTOCOL:
If the task requires another expert, add at the END of your answer (use LATIN names only):
HANDOFF: @ExpertName
TASK: task description for the colleague
CONTRACT: {"expected_output": "description", "format": "text"}

Available experts: @Igor (backend/code), @Dmitry (ML/models), @Sergey (DevOps/deploy),
@Anna (QA/tests), @Elena (monitoring/logs), @Alexey (security), @Roman (database),
@Olga (performance), @Maxim (analytics), @Pavel (trading strategy).
Use HANDOFF only if delegation genuinely improves the result.
"""
    if not is_discussion_mode and expert_name in ("Виктория", "Victoria", "виктория"):
        prompt = swarm_instruction + "\n" + prompt

    request_id = f"{expert_name}_{int(time.time())}"
    # Единый user_key/project_context: из аргумента, иначе MAIN_PROJECT (в т.ч. execute_assignments)
    user_key = session_id or "orchestrator"
    project_context = (
        project_context or os.getenv("MAIN_PROJECT", "atra-web-ide")
    ).strip() or os.getenv("MAIN_PROJECT", "atra-web-ide")
    user_part = prompt.split("Запрос:")[-1].strip() if "Запрос:" in prompt else prompt

    # Operational execution goals (dashboard/audit/no-clarify) should skip recursive meta-loops.
    # They require deterministic execution path and are prone to recursion overflow in discovery/debate.
    _upl = user_part.lower()
    is_operational_execution_goal = (
        ("аудит" in _upl or "deep-analysis" in _upl or "deep analysis" in _upl)
        and ("дашборд" in _upl or "dashboard" in _upl)
    ) or (
        any(m in _upl for m in ("без уточнений", "не задавай уточняющие", "сразу выполняй"))
        and any(m in _upl for m in ("исправ", "проверь", "sql", "миграц", "quality gate"))
    )

    # [SINGULARITY 20.0] Wisdom Injection: Meta-Strategies from Knowledge Base
    contexts = await inject_context_enrichment(expert_name, user_part, project_context)
    meta_wisdom_context = contexts["meta_wisdom"]
    mentorship_context = contexts["mentorship"]
    experience_context = contexts["experience"]
    constitution_context = contexts["constitution"]

    # --- [SINGULARITY 21.21] RECURSIVE TESTING PROMPT INJECTION ---
    recursive_test_instruction = """
### 🧪 RECURSIVE TESTING RULE:
Если ты предлагаешь новый код или изменяешь существующую логику, ты ОБЯЗАН предоставить авто-тест (pytest).
Твой ответ должен содержать блок кода с тестом, либо ты должен убедиться, что существующий тест в проекте покрывает твои изменения.
Без теста твоё решение будет отклонено ArchitecturalGuard.

### 🎯 FOCUS GUARD (Singularity 27.2):
Твоя задача — ответить на КОНКРЕТНЫЙ вопрос пользователя.
1. Сначала выдели ключевые параметры запроса (например: VRAM, модели, конкретные числа).
2. Если запрос технический, начни ответ с ФАКТОВ и ДАННЫХ, а не с теории.
3. ЗАПРЕЩЕНО уходить в общие рассуждения о "цифровой конституции" или "корпоративных стандартах", если об этом не просили напрямую.
4. В конце ответа проверь: "Ответил ли я на все числовые и технические параметры запроса?".
"""
    experience_context = recursive_test_instruction + "\n" + experience_context
    # --- END RECURSIVE TESTING ---

    # --- MODEL ENSEMBLE LOGIC (Phase 2.7) ---
    async def _introspection_loop(initial_prompt: str, initial_response: str) -> str:
        """[SINGULARITY 21.20] Introspection Loop: Self-criticism and refinement."""
        logger.info(f"🧠 [INTROSPECTION] Starting self-evaluation for {expert_name}")

        introspection_prompt = f"""Ты - Критик Сингулярности. Проведи интроспекцию ответа эксперта {expert_name}.
ИСХОДНЫЙ ЗАПРОС: {initial_prompt}
ОТВЕТ ЭКСПЕРТА: {initial_response}

КРИТЕРИИ ГИГАНТОВ:
1. First Principles: Решена ли задача в корне или это "костыль"?
2. Occam's Razor: Можно ли сделать это проще?
3. Reliability: Есть ли риски падения?

Если ответ идеален, верни 'PERFECT'. Если есть что улучшить, предложи финальную, отточенную версию."""

        try:
            if router:
                result = await router.run_local_llm(
                    introspection_prompt,
                    category="reasoning",
                    model_hint="lfm2.5-thinking",
                    expert_name=expert_name,
                )
                refined_text = result[0] if isinstance(result, tuple) else result

                if "PERFECT" in refined_text[:10]:
                    return initial_response

                logger.info("✨ [INTROSPECTION] Response refined by self-criticism.")
                return refined_text
            return initial_response
        except Exception as e:
            logger.error(f"❌ [INTROSPECTION] Error: {e}")
            return initial_response

    async def _verify_and_refine(initial_prompt: str, initial_response: str, depth: int = 0) -> str:
        """[SINGULARITY 21.22] Use EnsembleVerifier for cleaner logic."""
        from core.ensemble_verifier import EnsembleVerifier

        verifier = EnsembleVerifier(router, expert_name)
        return await verifier.verify_and_refine(initial_prompt, initial_response, depth)

    # 0. Anomaly Detection: проверка запроса на аномалии
    try:
        # [SINGULARITY 20.0] Collective Brainstorming for complex design tasks
        user_part_lower = user_part.lower()
        if (
            "brainstorm" in user_part_lower
            or "обсуди" in user_part_lower
            or "спроектируй" in user_part_lower
        ) and not session_id:
            logger.info("🧠 [BRAINSTORMING] Triggering Collective Brainstorming session...")
            from collective_brainstorming import run_brainstorming

            result = await run_brainstorming(user_part, "")
            return f"✅ Коллективное обсуждение завершено.\n\n### 🏛 Финальный дизайн\n{result['design']}\n\n### 📋 План реализации\n{result['plan']}\n\nПолный лог обсуждения сохранен в docs/plans/."

        # [SINGULARITY 10.0+] Multi-Agent Debate for critical tasks
        if is_critical and get_multi_agent_debate:
            logger.info("⚖️ [CRITICAL] Starting Multi-Agent Debate for critical task...")
            debate = get_multi_agent_debate()
            debate_result = await debate.run_debate(prompt)
            if debate_result and debate_result.final_decision:
                logger.info("✅ [DEBATE COMPLETE] Critical decision reached.")
                return debate_result.final_decision

        # [SINGULARITY 21.22] Use AnomalyDetectorBridge for cleaner logic
        from core.anomaly_bridge import AnomalyDetectorBridge

        should_block, alert = await AnomalyDetectorBridge.analyze_request(
            prompt, request_id, expert_name, category or "general"
        )

        if should_block:
            logger.warning(
                f"🚨 [ANOMALY DETECTOR] Запрос заблокирован: {alert.description if alert else 'unknown'}"
            )
            return "⚠️ Запрос отклонен системой безопасности."

        if AnomalyDetectorBridge.is_blocked(request_id):
            logger.warning(f"🚨 [ANOMALY DETECTOR] Идентификатор заблокирован: {request_id}")
            return "⚠️ Доступ временно ограничен. Попробуйте позже."

    except Exception as e:
        logger.debug(f"Anomaly detection failed: {e}")

    # 0.1. Disaster Recovery: проверка состояния системы
    disaster_recovery = None
    if get_disaster_recovery:
        disaster_recovery = get_disaster_recovery()
        await disaster_recovery.run_health_check()

        # Если система в режиме OFFLINE, возвращаем ошибку
        if disaster_recovery.get_current_mode() == SystemMode.OFFLINE:
            logger.error("🚨 [DISASTER RECOVERY] Система в режиме OFFLINE")
            return "⚠️ Система временно недоступна. Пожалуйста, попробуйте позже."

    # 1. Initialization (кэш в той же БД, что дашборд/SLA — DATABASE_URL)
    cache = SemanticAICache(db_url=os.getenv("DATABASE_URL")) if SemanticAICache else None

    # [SINGULARITY 10.0+] Параллельная проверка кэша, роутинга и контекста
    async def get_cache_and_context():
        # Запускаем параллельно: проверку кэша и получение контекста знаний (RAG с учётом project_context)
        tasks = []
        if cache and not images:
            tasks.append(cache.get_cached_response(user_part, expert_name))
        else:
            tasks.append(asyncio.sleep(0, result=None))

        tasks.append(_get_knowledge_context(user_part, project_context))

        return await asyncio.gather(*tasks)

    # 1.1. Проверка кэша и контекста (Singularity 10.0+)
    cached_response, kb_context_rag = await get_cache_and_context()

    if cached_response:
        logger.info(f"🎯 [CACHE HIT] Found similar query for expert {expert_name}")

        # [SINGULARITY 21.3] Record tokens saved for local provider on cache hit
        try:
            tokens_saved = len(str(cached_response)) // 4
            record_llm_request(
                provider="local",
                model="semantic-cache",
                input_tokens=len(user_part) // 4,
                output_tokens=tokens_saved,
            )
            logger.info(f"💰 [CACHE SAVINGS] Recorded ~{tokens_saved} tokens saved in Prometheus")
        except Exception as metrics_err:
            logger.debug(f"Failed to record cache hit metrics: {metrics_err}")

        return cached_response

    # Воркер передаёт роутер явно (local_router) или через _current_router.
    import sys

    _mod = sys.modules.get(__name__)
    _router_preferred = (
        local_router if local_router is not None else getattr(_mod, "_current_router", None)
    )
    if local_router is None and getattr(_mod, "_current_router", None) is not None:
        _mod._current_router = None  # сброс после взятия из глобала
    router = (
        _router_preferred
        if _router_preferred is not None
        else (_get_local_router() if LocalAIRouter else None)
    )
    distiller = _get_distiller()
    qa = QualityAssurance(min_quality_threshold=0.7) if QualityAssurance else None
    quality_gate = QualityGate(qa) if QualityGate and qa else None
    parallel_processor = ParallelProcessor(max_concurrent=3) if ParallelProcessor else None

    # ML Router v2 для предсказания оптимального роутинга (Singularity 8.0)
    ml_router_v2 = get_ml_router_v2() if get_ml_router_v2 else None
    predicted_route = None
    route_confidence = 0.0

    # Circuit breakers для критических компонентов
    db_breaker = (
        get_circuit_breaker("database", failure_threshold=5, recovery_timeout=60)
        if get_circuit_breaker
        else None
    )
    local_breaker = (
        get_circuit_breaker("local_models", failure_threshold=3, recovery_timeout=30)
        if get_circuit_breaker
        else None
    )
    cloud_breaker = (
        get_circuit_breaker("cloud", failure_threshold=3, recovery_timeout=30)
        if get_circuit_breaker
        else None
    )

    # 1.1. RAG: Поиск знаний в базе (учимся у коллег)
    kb_context = ""

    # [SINGULARITY 28.0] Long-term Memory Recall
    ltm_context = ""
    try:
        from long_term_memory import get_ltm

        ltm = get_ltm()
        memories = await ltm.recall_memories(user_part)
        if memories:
            ltm_context = "\n### 📜 LONG-TERM MEMORY (PAST SESSIONS):\n"
            for m in memories:
                ltm_context += f"- {m['content'][:500]}\n"
            logger.info(f"🧠 [LTM] Recalled {len(memories)} memories for {expert_name}")
    except Exception as ltm_err:
        logger.debug(f"LTM recall failed: {ltm_err}")

    # [SINGULARITY 20.0] Proactive Knowledge Utilization
    # Force RAG for all tasks to increase knowledge usage from 0.04%
    force_rag = os.getenv("FORCE_PROACTIVE_RAG", "true").lower() == "true"

    # Track usage in DB
    async def _track_knowledge_usage(node_ids: List[str]):
        if not node_ids:
            return
        pool = await _get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE knowledge_nodes SET usage_count = COALESCE(usage_count, 0) + 1 WHERE id = ANY($1)",
                    node_ids,
                )

    # МОНСТР-ЛОГИКА: Скелетное чтение для гигантских файлов
    if "app.py" in prompt or "dashboard" in prompt:
        try:
            from app.file_utils import get_file_skeleton

            file_path = "knowledge_os/dashboard/app.py"
            skeleton = get_file_skeleton(file_path)
            kb_context = f"\n### СТРУКТУРА ФАЙЛА (СКЕЛЕТ):\n{skeleton}\n---\n"
            logger.info(f"🐉 [MONSTER] Подмешан скелет файла {file_path} для экономии памяти")
            # Обрезаем основной промпт, если там был весь файл
            if len(prompt) > 5000:
                prompt = prompt[:1000] + "... [весь файл заменен скелетом для стабильности] ..."
        except Exception as fe:
            logger.debug(f"⚠️ [MONSTER] Ошибка создания скелета: {fe}")

    try:
        from app.model_enhancer import EnhancedRAGEngine

        rag_engine = EnhancedRAGEngine()
        # Ищем релевантные знания (включая результаты работы других экспертов)
        # [SINGULARITY 20.0] Increased limit and lower threshold for better utilization
        # Если force_rag=True, мы игнорируем некоторые фильтры для максимального охвата
        contexts = await rag_engine.retrieve_enhanced_context(
            prompt, limit=8 if force_rag else 5, min_confidence=0.3 if force_rag else 0.4
        )
        if contexts:
            # Track usage
            node_ids = [
                ctx.get("metadata", {}).get("id") or ctx.get("id")
                for ctx in contexts
                if ctx.get("metadata", {}).get("id") or ctx.get("id")
            ]
            if node_ids:
                asyncio.create_task(_track_knowledge_usage(node_ids))

                # [SINGULARITY 28.X] Log knowledge edges (links between query and retrieved knowledge)
                try:
                    pool = await _get_db_pool()
                    if pool and node_ids:

                        async def _log_knowledge_edges():
                            pool = await _get_db_pool()
                            if not pool:
                                return
                            async with pool.acquire() as conn:
                                # Generate edge from query to each retrieved node
                                query_hash = hash(prompt[:200])
                                for node_id in node_ids[:5]:  # Limit to top 5
                                    try:
                                        await conn.execute(
                                            """INSERT INTO knowledge_edges (source_id, target_id, relation_type, metadata)
                                            VALUES ($1, $2, 'used_in_query', $3)
                                            ON CONFLICT DO NOTHING""",
                                            f"query_{query_hash}",
                                            node_id,
                                            json.dumps({"expert": expert_name, "relevance": 0.8}),
                                        )
                                    except:
                                        pass

                        asyncio.create_task(_log_knowledge_edges())
                except Exception as ke:
                    logger.debug(f"⚠️ Knowledge edges logging failed: {ke}")

            kb_context = "\n### ЗНАНИЯ ОТ КОЛЛЕГ (ИЗ БАЗЫ ЗНАНИЙ):\n"

            # [SINGULARITY 14.2] Fact Extraction for long contexts
            total_context_len = sum(len(ctx["content"]) for ctx in contexts)
            if total_context_len > 3000:
                logger.info(
                    f"✂️ [FACT EXTRACTOR] Context too long ({total_context_len}), extracting facts..."
                )
                extractor = FactExtractor()
                full_text = "\n".join([ctx["content"] for ctx in contexts])
                kb_context += await extractor.extract_facts(
                    full_text, context_description=f"Expert: {expert_name}"
                )
            else:
                for i, ctx in enumerate(contexts, 1):
                    kb_context += f"Инсайт {i} (релевантность {ctx.get('relevance', 0):.2f}): {ctx['content']}\n---\n"

            logger.info(
                f"📚 [PROACTIVE RAG] Внедрено {len(contexts)} инсайтов для эксперта {expert_name}"
            )
    except Exception as re:
        logger.debug(f"⚠️ [RAG] Ошибка поиска знаний: {re}")

    # Подмешиваем знания коллег в промпт
    if (
        kb_context
        or ltm_context
        or meta_wisdom_context
        or mentorship_context
        or experience_context
        or constitution_context
    ):
        # [SINGULARITY 14.2] Use ContextSwapper for kb_context
        swapper = ContextSwapper()
        full_context = f"{constitution_context}\n{meta_wisdom_context}\n{mentorship_context}\n{experience_context}\n{ltm_context}\n{kb_context}"
        kb_context = await swapper.swap_if_needed(full_context, f"kb_context_{request_id}")
        user_part = f"{kb_context}\n\nЗАПРОС: {user_part}"

    # Проверка на запрос стратегии: автоматический запуск Discovery → MASTER_PLAN → декомпозиция
    is_strategy_request = False
    if QueryOrchestrator and not session_id:
        try:
            temp_orch = QueryOrchestrator()
            query_type = temp_orch.classify_query(user_part)
            is_strategy_request = query_type == QueryType.STRATEGY

            if category == "orchestrator_assignment":
                logger.info(
                    "[ORCHESTRATOR_ASSIGNMENT] Пропуск итеративного планирования для подзадачи."
                )
                # МОНСТР-ЛОГИКА: Для подзадач форсируем локальный роутинг
                if router:
                    router.force_local = True
                    logger.info(
                        "[ORCHESTRATOR_ASSIGNMENT] Форсирован локальный роутинг для подзадачи."
                    )
                is_strategy_request = False  # Принудительно отключаем стратегию для подзадач
        except Exception:
            pass

    # Если это запрос на стратегию и нет session_id, создаем сессию и запускаем Discovery
    if is_strategy_request and not session_id:
        try:
            from strategy_discovery import StrategyDiscovery
            from strategy_session_manager import StrategySessionManager

            session_manager = StrategySessionManager()
            new_session_id = session_manager.create_session(
                title=user_part[:100],  # Первые 100 символов как название
                description=user_part,
            )

            # Запускаем Discovery фазу
            discovery = StrategyDiscovery(session_manager, temp_orch)
            question_ids = await discovery.start_discovery(new_session_id, user_part)

            if question_ids:
                # Если есть вопросы, возвращаем их пользователю
                conn = session_manager._get_connection()
                cursor = conn.cursor()
                questions_text_parts = []
                for i, qid in enumerate(question_ids):
                    cursor.execute(
                        "SELECT question_text FROM strategy_questions WHERE id = ?", (qid,)
                    )
                    row = cursor.fetchone()
                    if row:
                        questions_text_parts.append(f"❓ Вопрос {i + 1}: {row['question_text']}")
                conn.close()

                questions_text = "\n".join(questions_text_parts)
                return f"📋 Discovery фаза начата для сессии {new_session_id}.\n\n{questions_text}\n\nПожалуйста, ответьте на вопросы для продолжения планирования."

            # Если вопросов нет, сразу переходим к планированию
            if discovery.is_ready_for_planning(new_session_id):
                from master_plan_generator import MasterPlanGenerator
                from plan_decomposer import PlanDecomposer

                generator = MasterPlanGenerator(
                    session_manager=session_manager, query_orch=temp_orch
                )
                plan_id = await generator.generate_master_plan(new_session_id)

                if plan_id:
                    decomposer = PlanDecomposer(
                        session_manager=session_manager, query_orch=temp_orch
                    )
                    await decomposer.decompose_master_plan(new_session_id)

                    return f"✅ MASTER_PLAN создан и декомпозирован для сессии {new_session_id}. План ID: {plan_id}"
        except Exception as e:
            logger.debug(f"⚠️ [ITERATIVE PLANNING] Ошибка автоматического планирования: {e}")
            # Продолжаем обычный путь

    # Обработка изображений (мультимодальность)
    if images and get_vision_processor:
        vision_processor = get_vision_processor()
        image_analysis = await vision_processor.describe_image(
            image_base64=images[0] if isinstance(images[0], str) else None
        )
        if image_analysis:
            user_part = f"Анализ изображения: {image_analysis}\n\nЗапрос: {user_part}"
            logger.info("🖼️ [VISION] Image analyzed locally (0 tokens)")

    # Оптимизация промпта для экономии токенов (с контролем качества)
    original_user_part = user_part  # Сохраняем оригинал для сравнения

    # Шаг 1: BE-Token замена (если доступна)
    if get_betoken_manager:
        try:
            betoken_manager = get_betoken_manager()
            user_part, token_used = betoken_manager.replace_with_token(user_part)
            if token_used:
                logger.info(f"🎯 [BE-TOKEN] Использован токен: {token_used}")
        except Exception as e:
            logger.debug(f"⚠️ [BE-TOKEN] Ошибка: {e}")

    # Шаг 2: FrugalPrompt сжатие (улучшенная техника)
    if FrugalPrompt:
        try:
            frugal_compressed = FrugalPrompt.compress(user_part, max_length=2000, aggressive=True)
            if len(frugal_compressed) < len(user_part):
                logger.info(
                    f"💰 [FRUGAL PROMPT] Сжато с {len(user_part)} до {len(frugal_compressed)} символов"
                )
                user_part = frugal_compressed
        except Exception as e:
            logger.debug(f"⚠️ [FRUGAL PROMPT] Ошибка: {e}")

    # Шаг 3: Fallback на PromptOptimizer (если FrugalPrompt недоступен)
    if PromptOptimizer and user_part == original_user_part:
        optimizer = PromptOptimizer()
        optimized_part = optimizer.remove_redundancy(user_part)
        optimized_part = optimizer.compress_prompt(optimized_part, max_length=2000)
        user_part = optimized_part

    # Quality Gate: проверяем, не снизило ли оптимизация качество
    if quality_gate and len(user_part) < len(original_user_part) * 0.5:
        # Если сжали более чем в 2 раза, проверяем качество
        if len(user_part) > 100:  # Минимальная длина для сохранения смысла
            logger.info(
                f"✅ [QUALITY GATE] Оптимизация применена: {len(original_user_part)} -> {len(user_part)} символов"
            )
        else:
            logger.warning("⚠️ [QUALITY GATE] Prompt optimization too aggressive, using original")
            user_part = original_user_part

    # 1.5. Определяем тип задачи (до Tacit Knowledge и кэша)
    _coding_keywords = [
        "код",
        "программируй",
        "рефакторинг",
        "тест",
        "аудит",
        "проверь",
        "напиши",
        "создай",
        "реализуй",
        "добавь",
        "исправь",
        "функци",
        "класс",
        "модуль",
        "api",
        "endpoint",
    ]
    is_coding_task = any(kw in user_part.lower() for kw in _coding_keywords)

    # 1.6. Tacit Knowledge Extractor: получаем стилевой профиль пользователя (Singularity 14.0)
    style_profile = None
    style_modifier = ""
    user_identifier = (
        session_id or "default_user"
    )  # Используем session_id как user_identifier или дефолт
    style_similarity_score = 0.0

    # 1.7. Emotional Response Modulation: детектируем эмоцию пользователя (Singularity 14.0)
    emotion_result = None
    emotion_modifier = ""

    if EmotionDetector:
        try:
            detector = EmotionDetector()
            emotion_result = await detector.detect_emotion_with_history(user_part, user_identifier)

            if emotion_result and emotion_result.confidence >= 0.5:  # MIN_EMOTION_CONFIDENCE = 0.5
                emotion_modifier = detector.create_style_modifier(emotion_result)
                logger.info(
                    f"😊 [EMOTION DETECTOR] Detected emotion: {emotion_result.detected_emotion} (confidence: {emotion_result.confidence:.2f})"
                )
        except Exception as e:
            logger.debug(f"⚠️ [EMOTION DETECTOR] Error detecting emotion: {e}")
            emotion_result = None

    if TacitKnowledgeMiner and is_coding_task:
        try:
            miner = TacitKnowledgeMiner()
            style_profile = await miner.get_style_profile(user_identifier)

            if style_profile and style_profile.preferences:
                # Формируем модификатор промпта на основе стилевых предпочтений
                prefs = style_profile.preferences
                style_modifier = f"""
СТИЛЕВЫЕ ПРЕДПОЧТЕНИЯ ПОЛЬЗОВАТЕЛЯ:
- Конвенция именования: {prefs.get("naming_convention", "snake_case")}
- Обработка ошибок: {prefs.get("error_handling", "defensive_with_exceptions")}
- Стиль тестирования: {prefs.get("testing_style", "tdd_with_pytest")}
- Стиль документации: {prefs.get("documentation_style", "detailed_docstrings")}
- Структура кода: {prefs.get("code_structure", "functional")}
- Именование переменных: {prefs.get("variable_naming", "descriptive_names")}
- Стиль функций: {prefs.get("function_style", "simple")}

ВАЖНО: Генерируй код строго в соответствии с этими предпочтениями.
"""
                logger.info(f"🎨 [TACIT KNOWLEDGE] Style profile loaded for user {user_identifier}")
        except Exception as e:
            logger.debug(f"⚠️ [TACIT KNOWLEDGE] Error loading style profile: {e}")
            style_profile = None

    # 2. Cache & Context Check (улучшенный) - через asyncio.gather
    # [SINGULARITY 14.2] Используем результаты из 1.1 (get_cache_and_context)
    # Переменные cached_response и kb_context_rag уже получены выше.
    knowledge_context = kb_context_rag or ""

    if cached_response:
        # Предиктивный префетчинг для следующих шагов
        if cache:
            asyncio.create_task(cache.prefetch_related_context(user_part))

        # Предсказательное кэширование: пред-генерируем ответы на вероятные запросы
        if PredictiveCache:
            pred_cache = PredictiveCache(cache)
            asyncio.create_task(pred_cache.predict_and_cache(user_part, expert_name))
        return cached_response

    # [SINGULARITY 22.8] Iterative Discovery
    # Если задача сложная и требует глубокого анализа, запускаем итеративную разведку
    # [SINGULARITY 22.8] Iterative Discovery Engine (RAG 3.0)
    # [SINGULARITY 29.5] Recursion Guard: Don't start discovery if already in a discovery/debate loop
    ctx = _RECURSION_CONTEXT.get()
    if (
        IterativeDiscovery
        and not is_operational_execution_goal
        and not ctx["discovery"]
        and not ctx["debate"]
        and ctx["depth"] < 3
        and (is_critical or category == "reasoning" or "#complex" in user_part.lower())
    ):
        logger.info(f"🕵️ [SINGULARITY 22.8] Starting Iterative Discovery for: {expert_name}")
        import sys

        # Update context for recursion guard
        new_ctx = ctx.copy()
        new_ctx["discovery"] = True
        new_ctx["depth"] = ctx["depth"] + 1
        token = _RECURSION_CONTEXT.set(new_ctx)

        try:
            ai_processor = sys.modules[__name__]
            discovery = IterativeDiscovery(ai_processor=ai_processor, max_iterations=3)
            return await discovery.run(
                user_part,
                expert_name,
                category or "general",
                context=knowledge_context,
                project_context=project_context,
            )
        finally:
            _RECURSION_CONTEXT.reset(token)

    # [SINGULARITY 22.1] Real-time Multi-Agent Debate
    # [SINGULARITY 29.5] Recursion Guard: Don't start debate if already in a discovery/debate loop
    if (
        ConsensusAgent
        and not is_operational_execution_goal
        and not ctx["debate"]
        and not ctx["discovery"]
        and ctx["depth"] < 3
        and (is_critical or category == "reasoning" or "обсуди" in user_part.lower())
    ):
        logger.info(
            f"🤝 [SINGULARITY 22.1] Starting Real-time Multi-Agent Debate for: {expert_name}"
        )
        # Update context for recursion guard
        new_ctx = ctx.copy()
        new_ctx["debate"] = True
        new_ctx["depth"] = ctx["depth"] + 1
        token = _RECURSION_CONTEXT.set(new_ctx)

        try:
            consensus = ConsensusAgent(
                model_name=os.getenv("VICTORIA_STRATEGIST_MODEL", "victoria-wisdom-v3.5:latest")
            )
            # Выбираем экспертов для дебатов на основе задачи
            debate_experts = ["Виктория", "Игорь", "Анна"]  # Базовая тройка
            if is_coding_task:
                debate_experts = ["Игорь", "Максим", "Виктория"]

            debate_res = await consensus.reach_consensus(
                debate_experts, user_part, {"kb_context": kb_context_rag}
            )
            if debate_res and debate_res.consensus_score > 0.7:
                logger.info(
                    f"✅ [SINGULARITY 22.1] Consensus reached with score {debate_res.consensus_score:.2f}"
                )
                # Сохраняем результат в кэш и возвращаем
                if cache:
                    await cache.save_to_cache(user_part, debate_res.final_answer, expert_name)
                return debate_res.final_answer
        finally:
            _RECURSION_CONTEXT.reset(token)

    # 3. Hybrid Strategy: Manager-Worker Pattern (Strategist vs Executor)
    # If the task is coding or audit, we use Strategist (Wisdom) to plan and Executor (Qwen3) to execute

    # [SINGULARITY 20.0] Load hybrid models from .env
    # Strategist = Victoria wisdom (plan); Executor = coder only when coding path needs it.
    # Both defaulting to qwen2.5-coder:14b kept a 14B model resident and starved board/MLX.
    strategist_model = os.getenv("VICTORIA_STRATEGIST_MODEL", "victoria-wisdom-v3.5:latest")
    executor_model = os.getenv("VICTORIA_EXECUTOR_MODEL", "qwen2.5-coder:14b")

    # [SINGULARITY 30.6] Local-First Orchestration: Force local strategist if ice_mode is off
    # [SINGULARITY 30.7] Temporarily disabled for R&D/Distillation VRAM offloading
    force_local_orchestration = os.getenv("VICTORIA_AUTONOMOUS_SWARM", "false").lower() == "true"
    try:
        try:
            from app.redis_manager import redis_manager
        except Exception:
            from redis_manager import redis_manager

        client = await redis_manager.get_client()
        ice_mode_val = await client.get("system:ice_mode")
        is_ice_mode = str(ice_mode_val).lower() in ("true", "1", "yes")

        if force_local_orchestration and not is_ice_mode:
            # Если мы не в Ice Mode, форсируем локальное планирование
            # Это уменьшает зависимость от облака (Singularity 30.6)
            logger.info(
                "🐝 [AUTONOMOUS SWARM] Local-First Orchestration active. Forcing local strategist."
            )
            # Мы не меняем саму модель, но router.run_local_llm будет вызван первым
    except Exception as e:
        logger.debug(f"Failed to check ice_mode for autonomous swarm: {e}")

    # Track token savings
    tokens_saved = 0

    # [SINGULARITY 10.0+] Episodic Memory (User preferences) — для всех задач, не только coding
    episodic_context = ""
    if get_episodic_memory_manager and not is_critical:
        em = get_episodic_memory_manager()
        episodic_context = await em.get_episodes(user_key, project_context)
        if episodic_context:
            knowledge_context = f"{episodic_context}\n\n{knowledge_context}"
            logger.info(f"💡 [EPISODIC] Loaded preferences for {user_key[:20]}")

    if is_coding_task and not is_critical:
        logger.info(
            f"👩‍💼 [STRATEGIST MODE] {strategist_model} is planning for {executor_model}..."
        )

        # [SINGULARITY 13.0] Self-Distillation Rules
        distilled_rules = ""
        if get_distillation_engine:
            de = get_distillation_engine()
            distilled_rules = await de.get_active_rules()
            if distilled_rules:
                knowledge_context = f"{distilled_rules}\n\n{knowledge_context}"

        # Phase 1: Strategist generates a TECHNICAL SPECIFICATION (MLX call)
        # [SINGULARITY 28.0] Agent A/B Testing: Select strategy/persona
        current_strategy = "default"
        try:
            from agent_ab_testing import get_agent_ab_testing

            ab_test = get_agent_ab_testing()
            current_strategy = await ab_test.select_strategy(
                expert_name, ["default", "concise", "creative"]
            )
            logger.info(f"⚖️ [AB TEST] Selected strategy '{current_strategy}' for {expert_name}")
        except Exception as ab_err:
            logger.debug(f"Agent A/B testing failed: {ab_err}")

        spec_prompt = f"""
        Вы - ВИКТОРИЯ, Главный Стратег (Wisdom Era). Составьте краткое ТЕХНИЧЕСКОЕ ЗАДАНИЕ (ТЗ) для младшего разработчика
        на основе запроса пользователя. Укажите только ЧТО сделать, без написания самого кода.

        СТРАТЕГИЯ ОТВЕТА: {current_strategy}

        {style_modifier}
        {emotion_modifier}

        ЗАПРОС: {user_part}
        """

        # [SINGULARITY 10.0+] Personality Adaptation (Anthropic pattern)
        if get_personality_manager:
            pm = get_personality_manager()
            spec_prompt = pm.adapt_prompt(user_part, spec_prompt)

        # Используем Strategist (Wisdom) на MLX/Ollama
        spec = None
        if router:
            # В Docker MLX часто недоступен из контейнера — предпочитаем Ollama для стратега,
            # чтобы реже срабатывал STRATEGIST FAILED и fallback на cursor-agent
            _in_docker_strategist = (
                os.path.exists("/.dockerenv")
                or os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
            )
            _saved_preferred = getattr(router, "_preferred_source", None)
            if _in_docker_strategist:
                # В Docker MLX часто недоступен из контейнера — предпочитаем Ollama для стратега,
                # но только если это НЕ модель Виктории (мозг Виктории всегда в MLX)
                if strategist_model and "victoria-wisdom-v3.5" in strategist_model.lower():
                    router._preferred_source = "mlx"
                else:
                    router._preferred_source = "ollama"
            try:
                spec_result = await router.run_local_llm(
                    spec_prompt,
                    category="reasoning",
                    model_hint=strategist_model,
                    expert_name=expert_name,
                )
                spec = spec_result[0] if isinstance(spec_result, tuple) else spec_result
            finally:
                if _in_docker_strategist:
                    router._preferred_source = _saved_preferred

        # Fallback to cloud if strategist failed
        if not spec or spec.startswith(("❌", "⚠️")):
            logger.warning("⚠️ [STRATEGIST FAILED] Falling back to cloud for planning...")
            spec = await _run_cloud_agent_async(
                spec_prompt, category="reasoning", is_vip=is_vip, expert_name=expert_name
            )

        if spec and not spec.startswith(("❌", "⚠️")):
            # Phase 2: Executor executes the spec (Ollama call)
            # Проверяем доступность локальных моделей через disaster recovery
            if disaster_recovery and not disaster_recovery.can_use_local_models():
                logger.warning(
                    "⚠️ [DISASTER RECOVERY] Локальные модели недоступны, используем облако"
                )
                local_result = None
            else:
                # Inject few-shot examples from distillation engine
                examples = ""
                if distiller:
                    try:
                        if db_breaker:
                            examples = await db_breaker.call(
                                distiller.get_relevant_examples, user_part, category or "coding"
                            )
                        else:
                            examples = await distiller.get_relevant_examples(
                                user_part, category or "coding"
                            )
                    except CircuitBreakerOpenError:
                        logger.warning(
                            "⚠️ [CIRCUIT BREAKER] Distillation engine недоступен, продолжаем без примеров"
                        )
                        examples = ""

                # Keep executor payload compact: large duplicated context degrades latency.
                def _clip_section(value: Any, max_len: int) -> str:
                    text = value if isinstance(value, str) else str(value or "")
                    text = text.strip()
                    if len(text) <= max_len:
                        return text
                    return text[:max_len].rstrip() + "\n...[truncated]"

                examples_compact = _clip_section(examples, 2500)
                style_compact = _clip_section(style_modifier, 600)
                emotion_compact = _clip_section(emotion_modifier, 400)
                spec_compact = _clip_section(spec, 5000)

                worker_prompt = (
                    f"{examples_compact}\n\n{style_compact}\n{emotion_compact}\n\n"
                    f"ТЗ ОТ СТРАТЕГА ({strategist_model}):\n{spec_compact}\n\n"
                    "ВЫПОЛНИТЕ ЗАДАНИЕ:"
                )
                logger.info(f"👷 [EXECUTOR START] {executor_model} executing TS locally...")

                # Используем Executor (Qwen3) на Ollama
                try:
                    if router:
                        local_result = await router.run_local_llm(
                            worker_prompt,
                            category="coding",
                            model_hint=executor_model,
                            expert_name=expert_name,
                        )
                    else:
                        local_result = None
                except Exception as e:
                    logger.warning(f"⚠️ [EXECUTOR FAILED] {e}")
                    local_result = None
            local_resp, routing_source = (
                local_result if isinstance(local_result, tuple) else (local_result, None)
            )

            # Quality Assurance: проверка качества ответа
            if local_resp and qa:
                is_acceptable, metrics, recommendation = await qa.validate_response(
                    local_resp, user_part, response_type="code", source="local"
                )

                if not is_acceptable:
                    logger.warning(
                        f"⚠️ [QUALITY CHECK] Local response quality {metrics.overall_score:.2f} below threshold"
                    )

                    # Собираем feedback о низком качестве
                    if get_feedback_collector:
                        collector = await get_feedback_collector()
                        await collector.collect_implicit_feedback(
                            query=user_part,
                            response=local_resp,
                            routing_source=routing_source or "local",
                            rerouted_to_cloud=True,
                            reroute_reason="low_quality",
                            quality_score=metrics.overall_score,
                        )

                    if recommendation == "reroute_to_cloud":
                        logger.warning("🔄 [QUALITY GATE] Rerouting to cloud due to low quality")

                        # В STRICT_LOCAL режиме не отдаём низкокачественный ответ
                        if is_strict_local():
                            logger.error("[STRICT_LOCAL] QA reroute_to_cloud заблокирован")
                            # Метрика
                            strict_local_qa_skip_count = getattr(
                                run_smart_agent_async, "_strict_local_qa_skip_count", 0
                            )
                            run_smart_agent_async._strict_local_qa_skip_count = (
                                strict_local_qa_skip_count + 1
                            )

                            # Один retry с изменённым промптом для улучшения качества
                            logger.info(
                                "[STRICT_LOCAL] Попытка retry локально с улучшенным промптом"
                            )
                            improved_prompt = (
                                "ВАЖНО: Улучши качество ответа — будь точнее, конкретнее, структурируй информацию. "
                                "Избегай неточностей и общих фраз.\n\n" + worker_prompt
                            )
                            try:
                                retry_resp = await router.run_local_llm(
                                    improved_prompt,
                                    category=category,
                                    is_vip=is_vip,
                                    expert_name=expert_name,
                                )
                                if isinstance(retry_resp, tuple):
                                    retry_resp = retry_resp[0]

                                if retry_resp and len(retry_resp) > 10:
                                    logger.info(
                                        "[STRICT_LOCAL] ✅ Retry с улучшенным промптом успешен"
                                    )
                                    local_resp = retry_resp
                                else:
                                    logger.error("[STRICT_LOCAL] ❌ Retry также низкого качества")
                                    local_resp = (
                                        "⚠️ Локальный ответ не прошёл проверку качества (QA score < порог). "
                                        "STRICT_LOCAL блокирует fallback на облако. "
                                        "Для сложных задач отключите STRICT_LOCAL или переформулируйте запрос."
                                    )
                            except Exception as retry_err:
                                logger.error(f"[STRICT_LOCAL] ❌ Retry exception: {retry_err}")
                                local_resp = "⚠️ Локальный ответ не прошёл проверку качества. STRICT_LOCAL блокирует fallback."
                        else:
                            # Обычный режим — fallback на облако
                            local_resp = None  # Force cloud fallback
                    elif recommendation == "retry_local":
                        logger.info("🔄 [QUALITY GATE] Retrying with local model...")
                        # Можно попробовать еще раз с другим промптом
                        # Пока просто перенаправляем в облако
                        local_resp = None

            # Safety check for local response (дополнительная проверка)
            if local_resp and SafetyChecker:
                checker = _get_safety_checker()
                if checker.should_reroute_to_cloud(local_resp, response_type="code"):
                    logger.warning(
                        "🛡️ [SAFETY CHECK] Local response failed safety check, rerouting to cloud"
                    )

                    # Собираем feedback о failed safety check
                    if get_feedback_collector:
                        collector = await get_feedback_collector()
                        await collector.collect_implicit_feedback(
                            query=user_part,
                            response=local_resp,
                            routing_source=routing_source or "local",
                            rerouted_to_cloud=True,
                            reroute_reason="safety_check_failed",
                        )

                    # В STRICT_LOCAL режиме не отдаём небезопасный ответ
                    if is_strict_local():
                        logger.error("[STRICT_LOCAL] Safety reroute_to_cloud заблокирован")
                        # Метрика
                        strict_local_safety_skip_count = getattr(
                            run_smart_agent_async, "_strict_local_safety_skip_count", 0
                        )
                        run_smart_agent_async._strict_local_safety_skip_count = (
                            strict_local_safety_skip_count + 1
                        )

                        # Один retry с изменённым промптом для улучшения безопасности
                        logger.info("[STRICT_LOCAL] Попытка retry локально с безопасным промптом")
                        safe_prompt = (
                            "СТРОГО: не используй hardcoded secrets, SQL injection, command injection. "
                            "Генерируй только безопасный код. Используй параметризованные запросы и проверку ввода.\n\n"
                            + worker_prompt
                        )
                        try:
                            retry_resp = await router.run_local_llm(
                                safe_prompt,
                                category=category,
                                is_vip=is_vip,
                                expert_name=expert_name,
                            )
                            if isinstance(retry_resp, tuple):
                                retry_resp = retry_resp[0]

                            # Проверяем retry на безопасность
                            if retry_resp and len(retry_resp) > 10:
                                if not checker.should_reroute_to_cloud(
                                    retry_resp, response_type="code"
                                ):
                                    logger.info(
                                        "[STRICT_LOCAL] ✅ Retry с безопасным промптом успешен"
                                    )
                                    local_resp = retry_resp
                                else:
                                    logger.error(
                                        "[STRICT_LOCAL] ❌ Retry также небезопасен, отклоняем"
                                    )
                                    local_resp = (
                                        "⚠️ Локальный ответ не прошёл проверку безопасности. "
                                        "STRICT_LOCAL блокирует fallback на облако. Задача отклонена. "
                                        "Проверьте промпт или отключите STRICT_LOCAL."
                                    )
                            else:
                                logger.error("[STRICT_LOCAL] ❌ Retry вернул пустой ответ")
                                local_resp = "⚠️ Локальный ответ не прошёл проверку безопасности. STRICT_LOCAL блокирует fallback."
                        except Exception as retry_err:
                            logger.error(f"[STRICT_LOCAL] ❌ Retry exception: {retry_err}")
                            local_resp = "⚠️ Локальный ответ не прошёл проверку безопасности. Задача отклонена."
                    else:
                        # Обычный режим — fallback на облако
                        local_resp = None  # Force cloud fallback

            # Fallback to cloud if local model failed or safety check failed
            if not local_resp:
                logger.warning(
                    "⚠️ [LOCAL FAILED] Local model returned None, falling back to cloud..."
                )
                # Use cloud for execution if local failed
                local_resp = await _run_cloud_agent_async(
                    worker_prompt, category="coding", is_vip=is_vip, expert_name=expert_name
                )
                if local_resp and not local_resp.startswith(("❌", "⚠️")):
                    logger.info("✅ [CLOUD FALLBACK] Cloud executed the task successfully")
                    if cache:
                        await cache.save_to_cache(user_part, local_resp, expert_name)
                    return local_resp

                # [SINGULARITY 28.X] ALWAYS log AB results after getting response
                _log_ab_id = f"{expert_name}_{abs(hash(str(local_resp)[:100])) % 1000000}"
                try:
                    pool = await _get_db_pool()
                    if pool:
                        async with pool.acquire() as conn:
                            await conn.execute(
                                """INSERT INTO agent_ab_results (expert_name, strategy, task_id, score, created_at)
                                VALUES ($1, $2, $3, 1.0, NOW())""",
                                expert_name,
                                current_strategy,
                                _log_ab_id,
                            )
                            logger.info(f"⚖️ [AB_LOG] {expert_name}/{current_strategy}/{_log_ab_id}")
                except Exception as _abe:
                    logger.debug(f"AB log error: {_abe}")

                if local_resp:
                    # --- MODEL ENSEMBLE ACTIVATION ---
                    if is_coding_task or is_critical:
                        local_resp = await _verify_and_refine(user_part, local_resp)

                    # Сохраняем метрики результата для ML-обучения
                    quality_metrics = None
                    if qa:
                        _, quality_metrics, _ = await qa.validate_response(
                            local_resp, user_part, response_type="code", source="local"
                        )

                # Phase 3: Strategist validates the result (Wisdom Era Audit)
                # [SINGULARITY 20.0] Mandatory Audit for Critical or High-Level Tasks
                is_critical_domain = any(
                    kw in str(category).lower() or kw in expert_name.lower()
                    for kw in ["backend", "database", "security", "infrastructure", "architecture"]
                )
                force_audit = os.getenv("ENFORCE_ARCHITECTURE_AUDIT", "true").lower() == "true"

                use_audit = os.getenv("USE_VICTORIA_AUDIT", "false").lower() in ("true", "1", "yes")

                # Если задача критическая и включен принудительный аудит, игнорируем USE_VICTORIA_AUDIT=false
                # Если задача критическая и включен принудительный аудит, игнорируем USE_VICTORIA_AUDIT=false
                should_run_audit = use_audit or (
                    force_audit and (is_critical or is_critical_domain)
                )

            # [FIX] Инициализируем заранее, чтобы избежать UnboundLocalError
            should_run_audit = bool(locals().get("should_run_audit", False))
            audit_result = None  # По умолчанию None (если аудит не нужен)
            style_similarity_score = 0.0  # [FIX] Инициализируем для UnboundLocalError
            if should_run_audit:
                logger.info(
                    f"🏛️ [ARCHITECTURAL OVERSIGHT] {strategist_model} is auditing {expert_name}'s work..."
                )
                audit_prompt = f"""
                    Вы - ВИКТОРИЯ, Главный Архитектор Корпорации (Level 20 Wisdom).
                    Проверьте код/решение, написанное экспертом {expert_name}.

                    КРИТЕРИИ ПРОВЕРКИ:
                    1. Соответствие корпоративным стандартам (SOP).
                    2. Безопасность и отсутствие уязвимостей.
                    3. Масштабируемость и чистота кода.

                    Если в коде есть критические ошибки или архитектурные нарушения, напишите ПЛАН ИСПРАВЛЕНИЯ.
                    Если решение отличное и соответствует стандартам, напишите только одно слово: 'APPROVED'.

                    РЕЗУЛЬТАТ ЭКСПЕРТА:
                    {local_resp}
                    """
                # Используем Strategist (Wisdom) на MLX для аудита
                if router:
                    audit_res = await router.run_local_llm(
                        audit_prompt,
                        category="reasoning",
                        model_hint=strategist_model,
                        is_vip=is_vip,
                        expert_name=expert_name,
                    )
                    audit_result = audit_res[0] if isinstance(audit_res, tuple) else audit_res
                else:
                    audit_result = await _run_cloud_agent_async(
                        audit_prompt,
                        category="reasoning",
                        is_vip=is_vip,
                        expert_name=expert_name,
                    )

                if audit_result and "APPROVED" not in audit_result.upper():
                    logger.warning(
                        f"⚠️ [AUDIT REJECTED] Victoria found issues in {expert_name}'s work."
                    )
                else:
                    logger.info(f"✅ [AUDIT APPROVED] Victoria approved {expert_name}'s work.")

            # [FIX] Проверяем audit_result на None перед использованием
            if audit_result is not None and audit_result and "APPROVED" in audit_result.upper():
                # Estimate token savings (local execution vs full cloud)
                estimated_cloud_tokens = len(user_part) // 4 + len(local_resp) // 4
                estimated_local_tokens = (
                    len(spec) // 4 + len(audit_result) // 4
                )  # Only planning + audit
                tokens_saved = estimated_cloud_tokens - estimated_local_tokens
                logger.info(
                    f"✅ [AUDIT PASSED] Code approved by Victoria. 💰 Tokens saved: ~{tokens_saved}"
                )

                # Tacit Knowledge: вычисляем style_similarity_score (Singularity 14.0)
                if TacitKnowledgeMiner and style_profile and local_resp:
                    try:
                        miner = TacitKnowledgeMiner()
                        style_similarity_score = await miner.calculate_style_similarity(
                            local_resp, user_identifier
                        )
                        logger.info(
                            f"🎨 [TACIT KNOWLEDGE] Style similarity: {style_similarity_score:.2f}"
                        )
                    except Exception as e:
                        logger.debug(f"⚠️ [TACIT KNOWLEDGE] Error calculating similarity: {e}")
                        style_similarity_score = 0.0

                # Use routing_source from router, fallback to "local" if not available
                final_routing_source = routing_source or "local"

                # Сохранение в кэш через circuit breaker (если БД доступна)
                if cache and disaster_recovery and disaster_recovery.can_write_to_db():
                    try:
                        if db_breaker:
                            await db_breaker.call(
                                cache.save_to_cache,
                                user_part,
                                local_resp,
                                expert_name,
                                routing_source=final_routing_source,
                                performance_score=1.0,  # Approved = high score
                                tokens_saved=tokens_saved,
                            )
                        else:
                            await cache.save_to_cache(
                                user_part,
                                local_resp,
                                expert_name,
                                routing_source=final_routing_source,
                                performance_score=1.0,  # Approved = high score
                                tokens_saved=tokens_saved,
                            )
                    except Exception as e:
                        logger.debug(f"Cache save failed: {e}")

                # Сохраняем финальные метрики результата для ML-обучения
                if get_collector:
                    try:
                        collector = await get_collector()
                        await collector.collect_routing_decision(
                            task_type="coding",
                            prompt_length=len(user_part),
                            category="coding",
                            selected_route=final_routing_source,
                            performance_score=1.0,  # Approved
                            tokens_saved=tokens_saved,
                            quality_score=quality_metrics.overall_score
                            if quality_metrics
                            else None,
                            success=True,
                            features={"expert_name": expert_name, "final_approved": True},
                        )
                    except CircuitBreakerOpenError:
                        logger.warning(
                            "⚠️ [CIRCUIT BREAKER] Не удалось сохранить в кэш, продолжаем без сохранения"
                        )
                elif cache and disaster_recovery:
                    logger.debug(
                        "⚠️ [DISASTER RECOVERY] БД недоступна для записи, пропускаем сохранение в кэш"
                    )

                # Сохраняем финальные метрики результата для ML-обучения
                if get_collector:
                    collector = await get_collector()
                    # Определяем routing_source если не был передан
                    actual_routing_source = routing_source or "local"
                    await collector.collect_routing_decision(
                        task_type="coding",
                        prompt_length=len(user_part),
                        category="coding",
                        selected_route=actual_routing_source,
                        performance_score=1.0,  # Approved
                        tokens_saved=tokens_saved,
                        quality_score=quality_metrics.overall_score if quality_metrics else None,
                        success=True,
                        features={"audit_result": "approved", "expert_name": expert_name},
                    )

                # Логируем style_similarity_score и emotion в metadata (Singularity 14.0)
                metadata_dict = {}
                if TacitKnowledgeMiner and style_similarity_score > 0:
                    metadata_dict["style_similarity"] = style_similarity_score
                    metadata_dict["user_identifier"] = user_identifier

                if emotion_result:
                    metadata_dict["detected_emotion"] = emotion_result.detected_emotion
                    metadata_dict["emotion_confidence"] = emotion_result.confidence
                    metadata_dict["tone_used"] = emotion_result.tone
                    metadata_dict["detail_level"] = emotion_result.detail_level

                # [SINGULARITY 28.0] Always log interaction for A/B testing
                interaction_log_id = None
                try:
                    from token_logger import log_ai_interaction

                    interaction_log_id = await log_ai_interaction(
                        prompt=user_part,
                        response=local_resp[:2000],
                        expert_name=expert_name,
                        model_type="local",
                        source="ai_core",
                        metadata=metadata_dict,
                    )
                except Exception as log_err:
                    logger.debug(f"Interaction log failed: {log_err}")
                    interaction_log_id = None

                # [SINGULARITY 28.0] Agent A/B Testing: Log result (always, even if log_id is None)
                final_score = 1.0
                try:
                    if quality_metrics:
                        final_score = quality_metrics.overall_score
                except:
                    pass

                log_id = (
                    str(interaction_log_id)
                    if interaction_log_id
                    else f"{expert_name}_{abs(hash(local_resp[:50])) % 100000}"
                )

                # Direct insert to avoid import issues
                try:
                    pool = await _get_db_pool()
                    if pool:
                        async with pool.acquire() as conn:
                            await conn.execute(
                                """INSERT INTO agent_ab_results (expert_name, strategy, task_id, score, created_at)
                                VALUES ($1, $2, $3, $4, NOW())""",
                                expert_name,
                                current_strategy,
                                log_id,
                                final_score,
                            )
                            logger.warning(
                                f"⚖️ [AB_TEST] INSERTED: {expert_name}/{current_strategy}/{log_id}/{final_score}"
                            )
                except Exception as ab_err:
                    logger.warning(f"⚖️ [AB_TEST] FAILED: {ab_err}")

                    # [SINGULARITY 28.X] Constitutional Rewards logging
                    try:
                        from constitutional_rewards import get_constitutional_rewards

                        rewards = get_constitutional_rewards()
                        reward_result = await rewards.evaluate_interaction(
                            prompt=user_part,
                            response=local_resp,
                            expert_name=expert_name,
                            interaction_log_id=str(interaction_log_id),
                        )
                        if reward_result.get("total") != 0:
                            logger.info(
                                f"⚖️ [REWARDS] {expert_name}: {reward_result.get('total'):.2f}"
                            )
                    except Exception as rew_err:
                        logger.debug(f"Constitutional rewards log failed: {rew_err}")

                    # Emotion Detection logging (only if emotion_result exists)
                    if emotion_result:
                        try:
                            detector = EmotionDetector()
                            feedback_score = None
                            await detector.log_emotion(
                                interaction_log_id, emotion_result, feedback_score
                            )
                        except Exception as e:
                            logger.debug(f"⚠️ [EMOTION DETECTOR] Error logging emotion: {e}")

                # [SINGULARITY 26.6] Quality Pipeline - call external service
                try:
                    import httpx

                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(
                            "http://quality-service:8003/quality/enhance",
                            json={
                                "prompt": prompt[:500],
                                "response": local_resp[:2000],
                                "enable_full": False,
                            },
                        )
                        if resp.status_code == 200:
                            result = resp.json()
                            local_resp = result["enhanced_response"]
                            metadata_dict["quality"] = result
                            logger.info(
                                f"✅ Quality: {result.get('quality', 0):.2f}, passed: {result.get('passed', False)}"
                            )
                except Exception as qe:
                    logger.debug(f"⚠️ Quality service unavailable: {qe}")

                # [SINGULARITY 28.X] Evaluate with Constitutional Rewards before returning
                try:
                    from constitutional_rewards import get_constitutional_rewards

                    rewards = get_constitutional_rewards()
                    response_time_seconds = float(metadata_dict.get("response_time_seconds", 0.0))
                    await rewards.evaluate_and_score(
                        interaction_log_id or "unknown",
                        expert_name,
                        local_resp,
                        {"response_time_seconds": response_time_seconds},
                    )
                except ImportError:
                    pass

                return local_resp
            else:
                # FEEDBACK LOOP: Send back to local with audit notes
                logger.warning(
                    "🔄 [REVISION NEEDED] Victoria found issues. Retrying locally with feedback..."
                )
                if distiller:
                    # Save the error for learning
                    expert_id = await _get_expert_id(expert_name)
                    if expert_id:  # Only save if expert_id is valid
                        save_correction_fn = getattr(distiller, "save_correction", None)
                        if callable(save_correction_fn):
                            await save_correction_fn(
                                expert_id,
                                category or "coding",
                                user_part,
                                local_resp,
                                "...",
                                audit_result,
                            )
                        else:
                            logger.debug(
                                "ℹ️ [DISTILLER] save_correction is not available; skip correction persistence"
                            )

                final_prompt = f"ПЛАН ИСПРАВЛЕНИЯ ОТ ТИМЛИДА:\n{audit_result}\n\nИСПРАВЬТЕ КОД:"
                final_result = await router.run_local_llm(
                    final_prompt, category="coding", expert_name=expert_name
                )
                final_resp, _ = (
                    final_result if isinstance(final_result, tuple) else (final_result, None)
                )
                if not final_resp:
                    logger.warning(
                        "⚠️ [REVISION FAILED] Local model failed on revision, returning original"
                    )
                    return local_resp
                return final_resp  # Return revised version

    # 4. Web-Enabled Local Route (Вероника с веб-поиском)
    # Проверяем, нужен ли веб-поиск (запросы о текущих событиях, новостях, трендах)
    needs_web_search = any(
        kw in user_part.lower()
        for kw in [
            "новости",
            "тренды",
            "сейчас",
            "текущие",
            "актуальные",
            "последние",
            "2025",
            "2024",
            "сегодня",
            "недавно",
            "latest",
            "recent",
        ]
    )

    # Для VIP/Reasoning задач (Совет) веб-поиск теперь разрешен, но с защитой от таймаутов
    if (is_vip or category in ("reasoning", "vip")) and needs_web_search:
        logger.info("🏛️ [BOARD WEB] Включен веб-поиск для стратегической задачи")

    use_local_route = bool(
        router and (images or router.should_use_local(prompt, category)) or needs_web_search
    )
    if use_local_route:
        logger.info(
            "🏠 [ROUTE] Выбран локальный маршрут (Ollama/MLX): images=%s, should_use_local=%s, needs_web=%s",
            bool(images),
            bool(router and router.should_use_local(prompt, category)),
            needs_web_search,
        )
    else:
        logger.info(
            "☁️ [ROUTE] Выбран облачный маршрут (сначала попробуем локальные внутри _run_cloud_agent_async): category=%s",
            category,
        )

    if router and (images or router.should_use_local(prompt, category)) or needs_web_search:
        # Если нужен веб-поиск, используем Веронику
        if needs_web_search and VeronicaWebResearcher:
            logger.info("🌐 [VERONICA WEB] Запрос требует веб-поиска, используем Веронику")
            veronica = VeronicaWebResearcher()
            result = await veronica.research_and_analyze(
                user_part,
                category=category or "research",
                use_web=True,
                timeout=1800.0 if (is_vip or category in ("reasoning", "vip")) else 120.0,
            )

            if result and result.get("analysis"):
                logger.info("✅ [VERONICA WEB] Ответ получен (0 токенов использовано!)")
                if cache:
                    await cache.save_to_cache(
                        user_part,
                        result["analysis"],
                        expert_name,
                        routing_source="veronica_web",
                        tokens_saved=len(result["analysis"]) // 4,  # Экономия от облака
                        performance_score=0.9,
                    )

                # Сохраняем данные о роутинге для ML-обучения
                if get_collector:
                    try:
                        collector = await get_collector()
                        await collector.collect_routing_decision(
                            task_type="research",
                            prompt_length=len(user_part),
                            category="research",
                            selected_route="veronica_web",
                            performance_score=0.9,
                            tokens_saved=len(result["analysis"]) // 4,
                            success=True,
                            features={"expert_name": expert_name, "web_search": True},
                        )
                    except Exception as e:
                        logger.debug(f"Failed to collect veronica routing data: {e}")

                return result["analysis"]

        # Параллельная обработка: локальные модели и облако одновременно
        # НО! Отключаем для reasoning задач (Совет, стратегия) - они требуют последовательной обработки
        use_parallel = (
            ParallelRequestProcessor
            and get_parallel_processor
            and router
            and category != "reasoning"  # ОТКЛЮЧАЕМ для reasoning!
            and not is_critical  # ОТКЛЮЧАЕМ для критичных задач
        )

        if use_parallel:
            logger.info("⚡ [PARALLEL] Параллельная обработка: локальные модели (облако отключено)")
            parallel_processor = get_parallel_processor(max_concurrent=3)

            # Создаем источники для параллельной обработки
            sources = []

            # Локальные модели (приоритет 1 - быстрее)
            async def try_local():
                if disaster_recovery and not disaster_recovery.can_use_local_models():
                    return None
                try:
                    if local_breaker:
                        result = await local_breaker.call(
                            router.run_local_llm,
                            prompt,
                            category=category,
                            images=images,
                            expert_name=expert_name,
                        )
                    else:
                        result = await router.run_local_llm(
                            prompt, category=category, images=images, expert_name=expert_name
                        )
                    if isinstance(result, tuple):
                        return result[0]
                    return result
                except Exception as e:
                    logger.debug(f"Local model failed in parallel: {e}")
                    return None

            sources.append(
                RequestSource(
                    name="local",
                    handler=try_local,
                    priority=1,
                    timeout=1800.0,  # Увеличено до 600s для тяжелых моделей
                )
            )

            # Облако отключено пользователем для обучения локальной системы
            # sources.append(RequestSource(
            #     name="cloud",
            #     handler=try_cloud,
            #     priority=2,
            #     timeout=300.0
            # ))

            # Параллельно обрабатываем источники
            response_source_name, response = await parallel_processor.process_parallel_sources(
                sources
            )

            if response:
                routing_source = (
                    f"{response_source_name}_parallel" if response_source_name else "parallel"
                )
                local_resp = response
                logger.info(f"✅ [PARALLEL] Получен ответ от {routing_source}")
            else:
                # Если параллельная обработка не дала результата, пробуем последовательно
                logger.warning(
                    "⚠️ [PARALLEL] Параллельная обработка не дала результата, пробуем последовательно"
                )
                if router:
                    logger.info("🏠 [LOCAL ROUTE] %s", expert_name)
                    local_result = await router.run_local_llm(
                        prompt, category=category, images=images, expert_name=expert_name
                    )
                    local_resp, routing_source = (
                        local_result if isinstance(local_result, tuple) else (local_result, None)
                    )
                else:
                    logger.warning(
                        "⚠️ [STRICT LOCAL] Local router unavailable, cloud fallback is DISABLED"
                    )
                    local_resp = None
                    routing_source = "failed_local_only"
        else:
            # Обычный локальный маршрут (без параллельной обработки)
            if router:
                logger.info("🏠 [LOCAL ROUTE] %s", expert_name)
                local_result = await router.run_local_llm(
                    prompt, category=category, images=images, is_vip=is_vip, expert_name=expert_name
                )
                local_resp, routing_source = (
                    local_result if isinstance(local_result, tuple) else (local_result, None)
                )
            else:
                # Fallback на облако отключен
                logger.warning(
                    "⚠️ [STRICT LOCAL] Local router unavailable, cloud fallback is DISABLED"
                )
                local_resp = None
                routing_source = "failed_local_only"

        # Safety check for direct local responses
        if local_resp and SafetyChecker:
            checker = _get_safety_checker()
            if checker.should_reroute_to_cloud(
                local_resp, response_type="code" if category == "coding" else "text"
            ):
                logger.warning("🛡️ [SAFETY CHECK] Local response failed, using cloud")

                # В STRICT_LOCAL режиме не отдаём небезопасный ответ
                if is_strict_local():
                    logger.error(
                        "[STRICT_LOCAL] Safety reroute_to_cloud заблокирован (direct local)"
                    )
                    # Метрика
                    strict_local_safety_skip_count = getattr(
                        run_smart_agent_async, "_strict_local_safety_skip_count", 0
                    )
                    run_smart_agent_async._strict_local_safety_skip_count = (
                        strict_local_safety_skip_count + 1
                    )

                    # Один retry с безопасным промптом
                    logger.info("[STRICT_LOCAL] Попытка retry локально с безопасным промптом")
                    safe_prompt = (
                        "СТРОГО: не используй hardcoded secrets, SQL injection, command injection. "
                        "Генерируй только безопасный код.\n\n" + prompt
                    )
                    try:
                        if router:
                            retry_resp = await router.run_local_llm(
                                safe_prompt,
                                category=category,
                                is_vip=is_vip,
                                expert_name=expert_name,
                            )
                            if isinstance(retry_resp, tuple):
                                retry_resp = retry_resp[0]

                            if retry_resp and len(retry_resp) > 10:
                                if not checker.should_reroute_to_cloud(
                                    retry_resp,
                                    response_type="code" if category == "coding" else "text",
                                ):
                                    logger.info(
                                        "[STRICT_LOCAL] ✅ Retry с безопасным промптом успешен"
                                    )
                                    local_resp = retry_resp
                                else:
                                    logger.error("[STRICT_LOCAL] ❌ Retry также небезопасен")
                                    local_resp = "⚠️ Локальный ответ не прошёл проверку безопасности. STRICT_LOCAL блокирует fallback. Задача отклонена."
                            else:
                                local_resp = "⚠️ Локальный ответ не прошёл проверку безопасности. STRICT_LOCAL блокирует fallback."
                        else:
                            local_resp = (
                                "⚠️ Локальный роутер недоступен. STRICT_LOCAL блокирует fallback."
                            )
                    except Exception as retry_err:
                        logger.error(f"[STRICT_LOCAL] ❌ Retry exception: {retry_err}")
                        local_resp = (
                            "⚠️ Локальный ответ не прошёл проверку безопасности. Задача отклонена."
                        )
                else:
                    # Обычный режим — fallback на облако
                    local_resp = None

            if local_resp:
                # --- MODEL ENSEMBLE ACTIVATION ---
                if is_coding_task or is_critical:
                    local_resp = await _verify_and_refine(prompt, local_resp)

                # Estimate savings for direct local usage
            estimated_cloud_tokens = len(prompt) // 4 + len(local_resp) // 4
            logger.info(
                f"💰 [TOKEN SAVINGS] Used local model, saved ~{estimated_cloud_tokens} tokens"
            )
            # Save to cache with routing info and quality metrics
            if cache:
                final_routing_source = routing_source or "local"

                # Получаем метрики качества для сохранения
                performance_score = 0.9  # Default
                if qa:
                    _, metrics, _ = await qa.validate_response(
                        local_resp, user_part, response_type="code", source="local"
                    )
                    performance_score = metrics.overall_score

                await cache.save_to_cache(
                    user_part,
                    local_resp,
                    expert_name,
                    routing_source=final_routing_source,
                    tokens_saved=estimated_cloud_tokens,
                    performance_score=performance_score,
                )

                # Сохраняем метрики результата для ML-обучения
                if get_collector:
                    collector = await get_collector()
                    # Определяем final_routing_source если не был передан
                    actual_routing_source = final_routing_source or routing_source or "local"
                    await collector.collect_routing_decision(
                        task_type="general",
                        prompt_length=len(user_part),
                        category=category,
                        selected_route=actual_routing_source,
                        performance_score=performance_score,
                        tokens_saved=estimated_cloud_tokens,
                        quality_score=metrics.overall_score if metrics else None,
                        success=True,
                        features={"expert_name": expert_name, "direct_local": True},
                    )

            # Сбор метрик производительности
            try:
                from metrics_collector import get_metrics_collector

                duration = time.time() - start_time
                metrics_collector = get_metrics_collector()
                # Оцениваем количество токенов (примерно 4 символа = 1 токен)
                estimated_tokens = len(local_resp) // 4
                await metrics_collector.collect_tokens_per_second(
                    estimated_tokens, duration, "local"
                )
            except Exception as e:
                logger.debug(f"Metrics collection failed: {e}")

            # [SINGULARITY 26.7] Offload complex tasks to Celery (fixes recursion)
            if len(user_part) > 100 or any(
                kw in user_part.lower()
                for kw in ["код", "code", "анализ", "analysis", "generate", "создай"]
            ):
                try:
                    from knowledge_os.app.celery_tasks import offload_to_celery

                    job_id = await offload_to_celery(prompt, expert_name, category)
                    local_resp = (
                        f"⏳ [Celery] Task queued: {job_id}. Check status at /api/tasks/{job_id}"
                    )
                    metadata_dict["celery_job_id"] = job_id
                except Exception as ce:
                    logger.warning(f"⚠️ Celery offload failed: {ce}")

            return local_resp

    # [SINGULARITY 28.X] FINAL AB LOG - catches all exit paths
    try:
        pool = await _get_db_pool()
        if pool and local_resp:
            _final_id = f"{expert_name}_{abs(hash(str(local_resp)[:100])) % 1000000}"
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO agent_ab_results (expert_name, strategy, task_id, score, created_at)
                    VALUES ($1, $2, $3, 1.0, NOW())""",
                    expert_name,
                    current_strategy,
                    _final_id,
                )
                logger.info(f"⚖️ [AB_FINAL] {expert_name}/{current_strategy}/{_final_id}")
    except Exception as _fabe:
        logger.debug(f"Final AB log error: {_fabe}")

    # 5. Query Orchestrator: нормализация запроса и сборка role-aware промпта
    query_orchestrator = None
    normalized_query = None
    optimized_role = expert_name

    # Инициализируем SessionManager если есть session_id
    session_manager = None
    if session_id:
        try:
            from strategy_session_manager import StrategySessionManager

            session_manager = StrategySessionManager()
        except Exception:
            pass

    if QueryOrchestrator and get_prompt_template:
        try:
            query_orchestrator = QueryOrchestrator(session_manager=session_manager)
            normalized_query = query_orchestrator.normalize_query(user_part)
            optimized_role = query_orchestrator.select_role(normalized_query.query_type)
            logger.info(
                f"🎯 [QUERY ORCHESTRATOR] Запрос нормализован: тип={normalized_query.query_type.value}, роль={optimized_role}"
            )
        except Exception as e:
            logger.debug(
                f"⚠️ [QUERY ORCHESTRATOR] Ошибка нормализации запроса: {e}, используем старый путь"
            )
            query_orchestrator = None

    # 6. Full Cloud Call (for Strategic / Architecture tasks). RAG с учётом project_context.
    knowledge_context = await _get_knowledge_context(user_part, project_context)

    # Если Query Orchestrator доступен, используем role-aware промпт
    if query_orchestrator and normalized_query and get_prompt_template:
        try:
            # Получаем контекст для промпта
            prompt_context = await query_orchestrator.select_context(
                session_id=session_id,  # Передаем session_id для восстановления контекста
                role=optimized_role,
                normalized_query=normalized_query,
            )

            # Оптимизируем контекст (сжатие до 70% окна)
            prompt_context = query_orchestrator.optimize_context(
                prompt_context, max_length=2000, max_window_percent=0.7
            )

            # Получаем шаблон роли
            role_template = get_prompt_template(optimized_role)
            # [SINGULARITY 21.8] Аудит setki-21 §6.5 п.4: блок «текущий проект» в инструкции эксперта
            if project_context and role_template:
                role_template = (
                    role_template.rstrip()
                    + "\n\nЕсли в запросе указан текущий проект — используй для поиска и ответов только контекст этого проекта.\n"
                )

            # Форматируем контекст
            context_str = query_orchestrator.format_context(prompt_context)
            structured_task = query_orchestrator.format_structured_task(normalized_query)

            # Добавляем knowledge_context если есть
            if knowledge_context:
                context_str = f"{context_str}\n\nДополнительный контекст:\n{knowledge_context}"

            # Собираем промпт через шаблон роли
            full_prompt = format_prompt(
                role_template,
                task=structured_task,
                context=context_str,
                constraints=", ".join(normalized_query.constraints)
                if normalized_query.constraints
                else "Нет",
                preferences=", ".join(normalized_query.preferences)
                if normalized_query.preferences
                else "Нет",
            )

            logger.info(
                f"✅ [QUERY ORCHESTRATOR] Промпт собран через шаблон роли: длина={len(full_prompt)}, роль={optimized_role}"
            )
        except Exception as e:
            logger.debug(
                f"⚠️ [QUERY ORCHESTRATOR] Ошибка сборки промпта: {e}, используем старый путь"
            )
            full_prompt = (knowledge_context + "\n" + prompt) if knowledge_context else prompt
    else:
        # Старый путь: просто объединяем промпт с контекстом
        full_prompt = (knowledge_context + "\n" + prompt) if knowledge_context else prompt

    # [SINGULARITY 21.8] Текущий проект: явная инструкция для ответов в рамках проекта (аудит setki-21)
    if project_context:
        project_line = f"\n### Текущий проект: {project_context}\nОтветы и поиск по коду/документам — только в рамках этого проекта.\n\n"
        full_prompt = project_line + full_prompt

    # [SINGULARITY 10.0+] Personality Adaptation (Anthropic pattern)
    if get_personality_manager:
        pm = get_personality_manager()
        full_prompt = pm.adapt_prompt(user_part, full_prompt)

    # [SINGULARITY 13.0] Recursive Self-Distillation: Inject learned rules
    if get_distillation_engine:
        de = get_distillation_engine()
        learned_rules = await de.get_active_rules(limit=3)
        if learned_rules:
            full_prompt = f"{full_prompt}\n\n{learned_rules}"
            logger.info("🧠 [DISTILLATION] Injected learned rules into prompt.")

    # [SINGULARITY 21.32] Memory Block System (Prompt Master)
    if session_id:
        try:
            ctx_mgr = get_session_context_manager()
            if ctx_mgr:
                # Получаем историю (последние 10 сообщений)
                # user_id в SessionContextManager — это session_id
                history_rows = await ctx_mgr.get_session_context(session_id, expert_name, user_part)
                # get_session_context возвращает строку, нам нужен список для get_memory_block
                # Но мы можем адаптировать get_memory_block или извлечь факты прямо здесь
                memory_block = get_memory_block([{"content": history_rows}])
                if memory_block:
                    full_prompt = memory_block + full_prompt
                    logger.info(f"🧠 [MEMORY BLOCK] Injected into prompt for session {session_id}")
        except Exception as e:
            logger.debug(f"⚠️ [MEMORY BLOCK] Error injecting memory: {e}")

    # [SINGULARITY 21.34] Instruction Re-injection (Giant's Knowledge)
    # Боремся с "центрифугированием инструкций" в длинных контекстах
    if len(full_prompt) > 8000:
        instruction_reminder = f"\n\n### [SYSTEM REMINDER: STAY IN CHARACTER]\nНапоминание: Ты {expert_name}. Следуй своим инструкциям и правилам 'Золотого стандарта' ATRA."
        full_prompt += instruction_reminder
        logger.info(
            f"🔄 [RE-INJECTION] System instructions re-injected for {expert_name} (len={len(full_prompt)})"
        )

    # [SINGULARITY 21.35] Confidence-Guided Self-Correction (CoRefine Pattern)
    # Если в промпте есть сомнение или задача сложная, добавляем инструкцию самопроверки
    if category in ("reasoning", "coding") or len(user_part) > 500:
        self_correct_instruction = "\n### [SYSTEM: SELF-CORRECTION ENABLED]\nЕсли ты не уверен в ответе на 100%, начни с анализа своих сомнений в теге <thought> и предложи альтернативный вариант."
        full_prompt += self_correct_instruction

    # [SINGULARITY 23.0] U-Shape Context Assembly (BOTTOM): Instruction Re-injection
    # Повторяем главную роль и правила в самом конце для борьбы с Lost in the Middle

    # [SINGULARITY 24.2] Local Team Discussion Hook
    if category == "team_discussion" or (
        isinstance(prompt, str) and "### TEAM_DISCUSSION" in prompt
    ):
        logger.info("🧠 [TEAM ENGINE] Intercepted team discussion request.")

        # Parse experts if provided in the prompt string
        selected_experts = ["Виктория", "Игорь", "Анна", "Дмитрий"]  # Default team
        task_title = "Team Discussion"
        task_description = prompt

        if isinstance(prompt, str) and "### EXPERTS:" in prompt:
            try:
                experts_line = [line for line in prompt.split("\n") if "### EXPERTS:" in line][0]
                selected_experts = [
                    e.strip() for e in experts_line.replace("### EXPERTS:", "").split(",")
                ]
            except Exception:
                pass

        if isinstance(prompt, str) and "### TASK:" in prompt:
            try:
                task_line = [line for line in prompt.split("\n") if "### TASK:" in line][0]
                task_title = task_line.replace("### TASK:", "").strip()
            except Exception:
                pass

        engine = TeamDiscussionEngine(router=router)
        try:
            discussion_result = await engine.generate_discussion(
                task_title=task_title,
                task_description=task_description,
                experts=selected_experts,
                context_data=knowledge_context,
            )

            # If the result is valid (not an error message), return it
            if (
                discussion_result
                and "Failed to generate team discussion locally" not in discussion_result
            ):
                return discussion_result

            logger.warning(
                "⚠️ [TEAM ENGINE] Local generation returned empty or error. Falling back to standard mode."
            )
        except Exception as e:
            logger.error(
                f"❌ [TEAM ENGINE] Error during local team generation: {e}. Falling back to standard mode."
            )

        # Fallback: continue to standard generation (cloud or standard local)
        # We modify the prompt to ensure it's handled as a normal request if the marker was present
        if isinstance(prompt, str):
            prompt = prompt.replace("### TEAM_DISCUSSION", "").strip()

    instruction_reinjection = f"""
### [ATTENTION ANCHOR: CORE MISSION]
Напоминание: Ты {expert_name}. Твоя цель — следовать 'Золотому стандарту' ATRA.
Используй <memory_crystals> из начала контекста как абсолютную истину.
ДЕЙСТВУЙ СТРОГО ПО ПРАВИЛАМ.
"""
    full_prompt += instruction_reinjection
    logger.info(f"⚓ [U-SHAPE] Instruction re-injected at the BOTTOM for {expert_name}")

    # [SINGULARITY 21.36] Agentic RAG 2.0 (Corrective RAG)
    # Если поиск по базе знаний не дал результатов, добавляем инструкцию перефразирования
    if knowledge_context and "результаты не найдены" in knowledge_context.lower():
        rag_2_0_instruction = "\n### [SYSTEM: AGENTIC RAG 2.0]\nРезультаты поиска по базе знаний не дали точных совпадений. Попробуй перефразировать ключевые термины или используй инструмент web_search для уточнения контекста."
        full_prompt += rag_2_0_instruction

    # Умное сокращение контекста перед отправкой в облако (агрессивное сжатие)
    # Predictive Compression: проверяем предсжатый контекст (Singularity 14.0)
    compressed_prompt = full_prompt
    latency_before_compression = time.time()
    latency_reduction = 0.0

    # [SINGULARITY 21.28] Оптимизация сжатия: повышаем пороги, чтобы не терять важный код
    _compression_threshold = int(os.getenv("CONTEXT_COMPRESSION_THRESHOLD", "32000"))
    _compression_limit = int(os.getenv("CONTEXT_COMPRESSION_LIMIT", "16000"))
    _compression_enabled = os.getenv("ENABLE_CONTEXT_COMPRESSION", "true").lower() in (
        "true",
        "1",
        "yes",
    )

    if _compression_enabled and ContextAnalyzer and len(full_prompt) > _compression_threshold:
        # Проверяем, есть ли предсжатый контекст (Predictive Compression)
        precompressed = None
        try:
            analyzer = ContextAnalyzer(relevance_threshold=0.65)
            precompressed = await analyzer.get_precompressed_context(user_part, user_identifier)

            if precompressed:
                compressed_prompt = precompressed
                latency_after_compression = time.time()
                latency_reduction = (
                    (
                        (latency_before_compression - latency_after_compression)
                        / latency_before_compression
                    )
                    if latency_before_compression > 0
                    else 0.0
                )
                tokens_saved = (len(full_prompt) - len(compressed_prompt)) // 4
                logger.info(
                    f"🚀 [PREDICTIVE COMPRESSION] Using precompressed context: {len(compressed_prompt)} chars (~{tokens_saved} tokens saved, latency ↓ {latency_reduction:.1%})"
                )
            else:
                # Обычное сжатие, если предсжатый контекст не найден
                analyzer = ContextAnalyzer(relevance_threshold=0.65)
                compressed_prompt = await analyzer.compress_context(
                    full_prompt, user_part, max_length=_compression_limit
                )
                tokens_saved = (len(full_prompt) - len(compressed_prompt)) // 4
                logger.info(
                    f"📉 [CONTEXT COMPRESSION] Compressed from {len(full_prompt)} to {len(compressed_prompt)} chars (~{tokens_saved} tokens saved)"
                )
        except Exception as e:
            logger.debug(f"⚠️ [PREDICTIVE COMPRESSION] Error checking precompressed context: {e}")
            # Fallback к обычному сжатию
            analyzer = ContextAnalyzer(relevance_threshold=0.65)
            compressed_prompt = await analyzer.compress_context(
                full_prompt, user_part, max_length=_compression_limit
            )
            tokens_saved = (len(full_prompt) - len(compressed_prompt)) // 4
            logger.info(
                f"📉 [CONTEXT COMPRESSION] Compressed from {len(full_prompt)} to {len(compressed_prompt)} chars (~{tokens_saved} tokens saved)"
            )
    elif _compression_enabled and ContextCompressor and len(full_prompt) > _compression_threshold:
        # Используем агрессивное сжатие
        compressed_prompt = await ContextCompressor.compress_smart(
            full_prompt, user_part, max_length=_compression_limit, aggressive=True
        )
        if len(compressed_prompt) < len(full_prompt):
            tokens_saved = (len(full_prompt) - len(compressed_prompt)) // 4
            logger.info(
                f"📉 [CONTEXT COMPRESSION] Compressed from {len(full_prompt)} to {len(compressed_prompt)} chars (~{tokens_saved} tokens saved)"
            )
        else:
            compressed_prompt = ContextCompressor.compress_all(full_prompt)

            # [SINGULARITY 10.0] Budget Gate Check
            try:
                from redis_manager import redis_manager

                rm = redis_manager
                client = await rm.get_client()
                daily_cost = await client.get(f"budget:daily:{expert_name or 'global'}")
                max_budget = float(os.getenv("DAILY_BUDGET_LIMIT", "10.0"))
                if daily_cost and float(daily_cost) >= max_budget:
                    logger.warning(
                        f"💰 [BUDGET GATE] Daily budget exceeded for {expert_name}. Forcing local model."
                    )
                    # Force local mode by returning local response directly if possible
                    if router:
                        return await router.run_local_llm(
                            prompt, category=category, expert_name=expert_name
                        )
            except Exception as budget_err:
                logger.debug(f"Budget check failed: {budget_err}")

            cloud_start_time = time.time()
            response = await _run_cloud_agent_async(
                compressed_prompt, category=category, is_vip=is_vip
            )
            response = await _safe_cloud_response(response)
            cloud_latency_ms = (time.time() - cloud_start_time) * 1000

            # [SINGULARITY 10.0] Record Cost in Redis
            try:
                from token_logger import estimate_tokens

                in_tokens = await estimate_tokens(compressed_prompt)
                out_tokens = await estimate_tokens(response or "")
                # Simple cost estimation for cloud
                estimated_cost = (in_tokens + out_tokens) * 0.00001  # $10 per 1M tokens avg
                await client.incrbyfloat(f"budget:daily:{expert_name or 'global'}", estimated_cost)
                await client.expire(f"budget:daily:{expert_name or 'global'}", 86400)
            except Exception as cost_err:
                logger.debug(f"Cost recording failed: {cost_err}")

    # Сохраняем данные о роутинге в облако для ML-обучения
    if get_collector and response:
        try:
            collector = await get_collector()
            await collector.collect_routing_decision(
                task_type="general",
                prompt_length=len(user_part),
                category=category,
                selected_route="cloud",
                performance_score=0.9,  # Cloud обычно хорош для сложных задач
                tokens_saved=0,  # Облако не экономит токены
                latency_ms=cloud_latency_ms,
                quality_score=None,  # Можно добавить QA проверку
                success=True,
                features={
                    "expert_name": expert_name,
                    "full_cloud_call": True,
                    "has_knowledge_context": bool(knowledge_context),
                    "prompt_compressed": len(compressed_prompt) < len(full_prompt),
                },
            )
            logger.debug("✅ [ML DATA] Saved cloud routing decision")
        except Exception as e:
            logger.debug(f"⚠️ [ML DATA] Failed to collect cloud routing data: {e}")

    # [SINGULARITY 14.0] Dynamic Expert Hiring for unknown technologies
    if response and (
        "не знаю" in response.lower()
        or "не знаком" in response.lower()
        or "unknown technology" in response.lower()
    ):
        if get_expert_hiring_manager:
            logger.info(
                "🕵️ [HIRING] Victoria detected a knowledge gap. Checking if a new expert is needed..."
            )
            hiring_manager = get_expert_hiring_manager()
            asyncio.create_task(hiring_manager.handle_new_technology(user_part, user_part))

    # [SINGULARITY 14.0] Hierarchical Memory: Resuscitate archived knowledge if needed
    if cache and get_hierarchical_memory_manager:
        # If confidence is low, we might want to check the archive
        # This is a simplified trigger
        pass

    # [SINGULARITY 12.0] Autonomous Tool Creation on failure
    if (
        response
        and (response.startswith("❌") or response.startswith("⚠️"))
        and get_autonomous_tool_creator
    ):
        _now = time.time()
        if _now - _last_tool_creator_log_time[0] >= 30:
            logger.info(
                "🛠️ [TOOL CREATOR] Attempting to create a missing tool to fix the failure..."
            )
            _last_tool_creator_log_time[0] = _now
        else:
            logger.debug(
                "🛠️ [TOOL CREATOR] Attempting to create a missing tool (throttled, see previous INFO)"
            )
        creator = get_autonomous_tool_creator()
        success = await creator.create_tool_on_the_fly(response, user_part)
        if success:
            logger.info("✅ [TOOL CREATOR] New tool created. Retrying task...")
            # Retry once with the new tool
            response = await _run_cloud_agent_async(compressed_prompt)
            response = await _safe_cloud_response(response)

    # Offline fallback
    if response and (response.startswith("❌") or response.startswith("⚠️")) and router:
        logger.warning("🛡️ [BUNKER MODE] Cloud failed, switching to Local.")
        return await router.run_local_llm(
            prompt, category=category, is_vip=is_vip, expert_name=expert_name
        )

    # Дополнение ответа внешними данными (Singularity 8.0)
    if response and not response.startswith(("⚠️", "❌")):
        try:
            from external_api_integration import get_external_api_integration

            external_api = get_external_api_integration()
            enhanced_response = await external_api.enhance_response_with_external_data(
                user_part, response
            )
            if enhanced_response and len(enhanced_response) > len(response):
                response = enhanced_response
                logger.info("🌐 [EXTERNAL API] Ответ дополнен внешними данными")
        except Exception as e:
            logger.debug(f"⚠️ [EXTERNAL API] Ошибка дополнения ответа: {e}")

    # Определяем финальный response если еще не определен
    if "response" not in locals():
        response = local_resp if "local_resp" in locals() else None

    if cache and response and not response.startswith(("⚠️", "❌")):
        await cache.save_to_cache(user_part, response, expert_name)

    # Сохранение контекста сессии (Singularity 8.0)
    if get_session_context_manager and response and not response.startswith(("⚠️", "❌")):
        try:
            # Получаем user_id из request_id (если доступен) или используем дефолтный
            user_id = request_id.split("_")[0] if "_" in request_id else "default"
            context_manager = get_session_context_manager()
            await context_manager.save_to_context(
                user_id=user_id, expert_name=expert_name, query=user_part, response=response
            )
        except Exception as e:
            logger.debug(f"⚠️ [SESSION CONTEXT] Ошибка сохранения контекста: {e}")

    # Логирование использования токенов (централизованное)
    if response and isinstance(response, str) and len(response) > 0:
        try:
            from token_logger import log_ai_interaction_fire_and_forget

            # Определяем модель на основе routing_source (если определен)
            model_type = "gpt-4o-mini"  # По умолчанию
            routing_src = None
            try:
                if "routing_source" in locals() or "routing_source" in globals():
                    routing_src = locals().get("routing_source") or globals().get("routing_source")
                elif "local_resp" in locals() and locals().get("local_resp"):
                    routing_src = "local"  # Если использован local_resp, значит локальная модель
            except Exception as e:
                logger.debug("Определение routing_source: %s", e)
            if routing_src:
                if "local" in str(routing_src).lower():
                    model_type = "local"
                elif "cloud" in str(routing_src).lower() or routing_src == "cloud_fallback":
                    model_type = "gpt-4o-mini"
                elif routing_src == "cursor-agent":
                    model_type = "cursor-agent"

            # Извлекаем использованные знания из кэша (если доступен)
            knowledge_ids = None
            knowledge_applied = False
            if cache:
                # Попытка получить информацию о знаниях из кэша
                try:
                    cache_info = await cache.get_cache_info(user_part)
                    if cache_info and cache_info.get("knowledge_nodes"):
                        knowledge_ids = cache_info.get("knowledge_node_ids", [])
                        knowledge_applied = bool(knowledge_ids)
                except Exception as e:
                    logger.debug("get_cache_info: %s", e)

            # Логируем использование токенов (fire and forget - не блокирует ответ)
            # Формируем metadata для логирования (Singularity 14.0 - Predictive Compression)
            metadata_for_logging = {}
            if latency_reduction > 0:
                metadata_for_logging["latency_reduction"] = latency_reduction
                metadata_for_logging["predictive_compression_used"] = True

            log_ai_interaction_fire_and_forget(
                prompt=user_part,
                response=response,
                expert_id=None,  # Будет найден по имени
                expert_name=expert_name,
                model_type=model_type,
                source="ai_core",
                knowledge_ids=knowledge_ids,
                knowledge_applied=knowledge_applied,
                category=category,
                metadata=metadata_for_logging if metadata_for_logging else None,
            )
        except Exception as e:
            logger.debug(f"⚠️ [TOKEN LOGGING] Ошибка логирования токенов: {e}")

    # Сбор метрик производительности для облачных ответов
    try:
        from metrics_collector import get_metrics_collector

        duration = time.time() - start_time
        metrics_collector = get_metrics_collector()
        # Оцениваем количество токенов (примерно 4 символа = 1 токен)
        estimated_tokens = len(response) // 4 if response else 0
        if estimated_tokens > 0 and duration > 0:
            await metrics_collector.collect_tokens_per_second(estimated_tokens, duration, "cloud")
    except Exception as e:
        logger.debug(f"Metrics collection failed: {e}")

    # [SINGULARITY 10.0+] Save to Episodic Memory if important patterns detected
    if (
        get_episodic_memory_manager
        and user_identifier
        and response
        and not response.startswith(("⚠️", "❌"))
    ):
        # Simple heuristic: if user gives specific style instructions or repeats a preference
        em = get_episodic_memory_manager()
        # project_context comes from outer scope or defaults
        p_ctx = locals().get("project_context") or os.getenv("MAIN_PROJECT", "atra-web-ide")
        if any(
            kw in user_part.lower()
            for kw in [
                "всегда",
                "никогда",
                "предпочитаю",
                "мне нравится",
                "используй только",
                "always",
                "never",
                "prefer",
                "i like",
                "i use",
                "i want",
                "always use",
                "never use",
                "my preference",
                "i usually",
                "i tend to",
                "i'd like",
                "i prefer",
                "i need",
                "i want you to",
                "from now on",
            ]
        ):
            asyncio.create_task(em.save_episode(user_identifier, p_ctx, "preference", user_part))
        elif "почему" in user_part.lower() and len(response) > 500:
            asyncio.create_task(
                em.save_episode(
                    user_identifier,
                    p_ctx,
                    "decision",
                    f"Detailed explanation for: {user_part[:50]}...",
                )
            )

    # [SINGULARITY 23.0] Crystallization Hook: Extract new crystals from response
    if response and not response.startswith(("⚠️", "❌")):

        async def _crystallize_task(text: str, p_ctx: str, pool):
            """Extracts decisions/parameters from response and saves as crystals."""
            if not pool:
                return

            # [SINGULARITY 23.6] Offload heavy regex and JSON to thread pool
            def _extract_sync():
                patterns = [
                    (r"Решили\s+использовать\s+([a-zA-Z0-9\s\.\-_]+)", "decision"),
                    (r"Порт:\s+(\d+)", "parameter"),
                    (r"Версия:\s+([vV]\d+\.\d+)", "milestone"),
                    (r"Стандарт:\s+([a-zA-Z0-9\s\.\-_]+)", "fact"),
                ]
                extracted = []
                for pattern, c_type in patterns:
                    import re

                    matches = re.findall(pattern, text, re.IGNORECASE)
                    for match in matches:
                        extracted.append((c_type, match.strip()))
                return extracted

            extracted_crystals = await asyncio.to_thread(_extract_sync)

            for c_type, content in extracted_crystals:
                try:
                    async with pool.acquire() as conn:
                        metadata_json = await asyncio.to_thread(
                            json.dumps, {"source": "auto_crystallizer"}
                        )
                        await conn.execute(
                            "INSERT INTO memory_crystals (project_context, crystal_type, content, metadata) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                            p_ctx,
                            c_type,
                            content,
                            metadata_json,
                        )
                        logger.info(f"💎 [CRYSTALLIZER] New crystal saved: {content}")
                except Exception as e:
                    logger.debug(f"Crystallization save failed: {e}")

        asyncio.create_task(_crystallize_task(response, project_context, pool))

    # [SINGULARITY 14.0] Shadow Prompt Evolution: Trigger shadow execution if mutations exist
    if response and not response.startswith(("⚠️", "❌")):
        asyncio.create_task(
            _trigger_shadow_execution(
                prompt=user_part,
                expert_name=expert_name,
                production_response=response,
                request_id=request_id,
                category=category,
            )
        )

    # [SINGULARITY 31.3] Canary Router: A/B test expert mutations in production
    if response and not response.startswith("[SYSTEM:") and expert_name != "Виктория":
        try:
            _canary_expert_id = _get_expert_id(expert_name)
            if inspect.isawaitable(_canary_expert_id):
                _canary_expert_id = await _canary_expert_id
            if _canary_expert_id:
                from app.canary_router import record_canary_result, should_use_canary

                _use_canary, _mutation = await should_use_canary(
                    expert_name, str(_canary_expert_id)
                )
                if _use_canary and _mutation:
                    # Run mutated prompt
                    _mutated_prompt = _mutation.get("mutated_prompt", "")
                    if _mutated_prompt:
                        _canary_response = await _run_cloud_agent_async(
                            _mutated_prompt, category=category, is_vip=False
                        )
                        asyncio.create_task(
                            record_canary_result(
                                mutation_id=_mutation["id"],
                                production_response=response,
                                canary_response=_canary_response,
                                expert_name=expert_name,
                            )
                        )
        except Exception as _canary_err:
            logger.debug(f"[CANARY] Skipped: {_canary_err}")

    # Cleanup internal metadata markers from response
    response = _clean_response(response)
    response = strip_think_blocks(response)

    return response


def _clean_response(response: str) -> str:
    """Remove internal orchestration markers and system errors from response."""
    if not response or not isinstance(response, str):
        return response

    # Remove system error messages
    if "[SYSTEM:" in response or response.startswith("⚠️") or response.startswith("❌"):
        return ""

    lines = response.split("\n")
    cleaned = []
    markers = (
        "Solved:",
        "ЗАДАЧА:",
        "План от",
        "Результаты работы",
        "Назначения оркестратора:",
        "Стратегия оркестратора:",
        "strategy_line",
        "[SYSTEM:",
        "⚠️",
        "❌",
    )
    for line in lines:
        stripped = line.strip()
        if not any(stripped.startswith(m) for m in markers):
            cleaned.append(line)
    return "\n".join(cleaned)


async def _trigger_shadow_execution(
    prompt: str,
    expert_name: str,
    production_response: str,
    request_id: str,
    category: Optional[str] = None,
):
    """
    [SINGULARITY 14.0] Shadow Execution Trigger.
    Checks for active shadow mutations and runs them in the background.
    """
    # Keep execution path testable even when optional manager is unavailable.
    if not ShadowExecutionManager:
        logger.debug("ShadowExecutionManager unavailable, continuing with lightweight trigger path")

    # [SINGULARITY 31.3] Shadow Execution v2: log performance for monitoring
    try:
        from app.shadow_execution_manager_v2 import get_shadow_manager as get_shadow_v2

        shadow_v2 = get_shadow_v2()
        shadow_v2.performance_metrics[request_id] = {
            "expert": expert_name,
            "category": category,
            "response_length": len(production_response or ""),
            "timestamp": time.time(),
        }
        logger.debug(f"[SHADOW_V2] Metrics logged for {request_id}")
    except Exception:
        pass

    try:
        pool = await _get_db_pool()
        if not pool:
            return

        # 1. Check for active shadow mutations for this expert
        acquired = pool.acquire()
        if inspect.isawaitable(acquired):
            acquired = await acquired
        if hasattr(acquired, "__aenter__"):
            conn_cm = acquired
        else:

            class _ConnPassthrough:
                def __init__(self, conn):
                    self._conn = conn

                async def __aenter__(self):
                    return self._conn

                async def __aexit__(self, exc_type, exc, tb):
                    release = getattr(pool, "release", None)
                    if callable(release):
                        maybe = release(self._conn)
                        if inspect.isawaitable(maybe):
                            await maybe
                    return False

            conn_cm = _ConnPassthrough(acquired)

        async with conn_cm as conn:
            expert_id = _get_expert_id(expert_name)
            if inspect.isawaitable(expert_id):
                expert_id = await expert_id
            if not expert_id:
                return

            mutations = await conn.fetch(
                """
                SELECT id, mutated_prompt
                FROM expert_mutations
                WHERE expert_id = $1 AND status = 'shadow'
                LIMIT 5
            """,
                expert_id,
            )

            if not mutations:
                return

            logger.info(f"👻 [SHADOW] Found {len(mutations)} shadow mutations for {expert_name}")

            # 2. Run shadow versions
            for mut in mutations:
                mutation_id = mut["id"]
                mutated_prompt_template = mut["mutated_prompt"]

                # Construct the full prompt with the mutated template
                # Note: This assumes the mutated_prompt in DB is a template or we just use it as is
                # for now we'll treat it as a replacement for the system/expert part if possible
                # but a simpler approach for Task 2 is to just run the prompt through the mutated version

                shadow_prompt = f"{mutated_prompt_template}\n\nUSER REQUEST: {prompt}"

                # We use _run_cloud_agent_async or router.run_local_llm for shadow
                # For now, let's use the same routing logic as the main request if possible,
                # or just a default local model to save costs.

                async def run_shadow():
                    try:
                        # Use local router for shadow execution to save tokens
                        if LocalAIRouter:
                            router = _get_local_router()
                            res = await router.run_local_llm(
                                shadow_prompt,
                                category=category or "general",
                                expert_name=expert_name,
                            )
                            return res[0] if isinstance(res, tuple) else res
                        else:
                            return await _run_cloud_agent_async(shadow_prompt)
                    except Exception as e:
                        logger.error(
                            f"❌ [SHADOW] Execution failed for mutation {mutation_id}: {e}"
                        )
                        return None

                shadow_response = await run_shadow()

                if shadow_response:
                    # 3. Send both to Evaluator
                    logger.info(
                        f"⚖️ [SHADOW] Sending results for mutation {mutation_id} to evaluator (Placeholder)"
                    )
                    if ShadowEvaluator:
                        logger.info(f"⚖️ [SHADOW] Evaluating mutation {mutation_id}...")
                        evaluator = ShadowEvaluator(db_url=os.getenv("DATABASE_URL"))
                        asyncio.create_task(
                            evaluator.evaluate_and_update(
                                mutation_id=mutation_id,
                                query=prompt,
                                prod_resp=production_response,
                                shadow_resp=shadow_response,
                            )
                        )
                    else:
                        logger.debug(
                            "ShadowEvaluator not available, kept placeholder-only logging for %s",
                            mutation_id,
                        )

    except Exception as e:
        logger.error(f"⚠️ [SHADOW] Trigger error: {e}")


async def _get_expert_id(name: str) -> str:
    """Helper to get expert UUID from DB."""
    try:
        from app.expert_aliases import resolve_expert_name_for_db

        resolved = resolve_expert_name_for_db(name)
    except ImportError:
        n = (name or "").strip()
        resolved = {
            "Veronica": "Вероника",
            "veronica": "Вероника",
            "VERONICA": "Вероника",
            "Victoria": "Виктория",
            "victoria": "Виктория",
            "VICTORIA": "Виктория",
        }.get(n, name)
    pool = await _get_db_pool()
    if not pool:
        return None
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT id FROM experts WHERE name = $1", resolved)


# [SINGULARITY 31.3] Background canary daemon — тестирует мутации без трафика
async def _canary_daemon_loop():
    """Run untested shadow mutations every hour."""
    while True:
        try:
            from app.canary_router import run_canary_daemon

            tested = await run_canary_daemon()
            if tested:
                logger.info(f"[CANARY_DAEMON] Tested {tested} untested mutations")
        except Exception:
            pass
        await asyncio.sleep(3600)  # every hour


try:
    # Avoid creating coroutine object when no running event loop is present.
    _loop = asyncio.get_running_loop()
except RuntimeError:
    _loop = None

if _loop and not _loop.is_closed():
    if not getattr(_loop, "_atra_canary_daemon_started", False):
        _loop.create_task(_canary_daemon_loop())
        setattr(_loop, "_atra_canary_daemon_started", True)
        logger.info("[CANARY_DAEMON] Started (hourly cycle)")
    else:
        logger.info("[CANARY_DAEMON] Already running for this event loop")
else:
    logger.info("[CANARY_DAEMON] Deferred start: no running loop at import time")
