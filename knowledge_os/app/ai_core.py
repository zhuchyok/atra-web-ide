"""
[SINGULARITY CORE] AI Agent Coordination Module.
Handles caching, routing, knowledge retrieval (RAG), and consensus across agents.
Optimized for Hybrid Intelligence (Cloud Architect + Local Worker).
"""

import asyncio
import getpass
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

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

    async def get_embedding(text: str) -> Optional[List[float]]:
        return None


try:
    from local_router import LocalAIRouter  # type: ignore
except ImportError:
    LocalAIRouter = None  # type: ignore

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
        try:
            from redis_manager import redis_manager
        except ImportError:
            from app.redis_manager import redis_manager

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

# Retry config for transient LLM failures (503, timeout, connection)
RETRY_BACKOFF_DELAYS = (2, 5, 10)  # seconds
RETRY_MAX_ATTEMPTS = 3

# Global user identification for conditional logic
USER_NAME = getpass.getuser()


def _is_transient_llm_error(e_or_msg) -> bool:
    """Check if error/message indicates transient LLM failure (503, timeout, etc.)."""
    if e_or_msg is None:
        return False
    s = str(e_or_msg).lower()
    return (
        "503" in s
        or "queue is full" in s
        or "timeout" in s
        or "connection" in s
        or "unavailable" in s
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
                os.getenv("DATABASE_URL") or "postgresql://admin:secret@localhost:5432/knowledge_os"
            )
            db_url = os.getenv("DATABASE_URL_LOCAL", default_url)
            _DB_POOL = await asyncpg.create_pool(
                db_url,
                min_size=1,
                max_size=5,  # Уменьшено для предотвращения перегрузки БД
                max_inactive_connection_lifetime=300,
            )
        except Exception as exc:
            logger.error("❌ Failed to create DB pool: %s", exc)
    return _DB_POOL


async def _run_cloud_agent_async(prompt: str):
    """Приоритет: локальные модели (Ollama/MLX) → cursor-agent. Локальные модели корпорации используются первыми."""
    # ПРИОРИТЕТ 1: локальные модели (Ollama/MLX) — политика корпорации
    # Health check перед запросом (2.3 плана): пропускаем заведомо недоступные узлы
    use_local = bool(LocalAIRouter)
    if use_local:
        try:
            _router = LocalAIRouter()
            healthy = await _router.check_health(force_refresh=False)
            if not healthy:
                logger.info("[HEALTH CHECK] No healthy local nodes, skipping to cloud/cursor-agent")
                use_local = False
        except Exception as hc_err:
            logger.debug("[HEALTH CHECK] Error: %s, will try local anyway", hc_err)
    if use_local and LocalAIRouter:

        async def _try_local():
            router = LocalAIRouter()
            result = await router.run_local_llm(prompt, category="general")
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
            logger.warning(
                "⚠️ [LOCAL FIRST] Локальный роутер недоступен: %s, пробуем cursor-agent", e
            )

    # ПРИОРИТЕТ 2: cursor-agent (облако) — только если локальные модели недоступны
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
                    router = LocalAIRouter()
                    # Быстрый fallback на локальные модели с таймаутом 15 секунд
                    result = await asyncio.wait_for(
                        router.run_local_llm(prompt, category="general"), timeout=15
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
        # 🍎 ПРИОРИТЕТ 1: Попробовать MLX (Apple Neural Engine) на Mac Studio
        try:
            from knowledge_os.app.mlx_router import get_mlx_router, is_mlx_available

            if is_mlx_available():
                mlx_router = get_mlx_router()
                logger.info("🍎 [MLX] Пробуем использовать Apple MLX (Neural Engine) на Mac Studio")
                mlx_response = await mlx_router.generate_response(
                    prompt=prompt, max_tokens=512, temperature=0.7
                )
                if mlx_response and len(mlx_response) > 10:
                    logger.info("✅ [MLX] Использован Apple MLX (Neural Engine) на Mac Studio")
                    return mlx_response
                else:
                    logger.debug("⚠️ [MLX] MLX не вернул ответ, пробуем Ollama")
        except ImportError:
            logger.debug("⚠️ MLX Router недоступен, пробуем Ollama")
        except Exception as e:
            logger.debug(f"⚠️ [MLX] Ошибка при использовании MLX: {e}, пробуем Ollama")

            # ПРИОРИТЕТ 2: cursor-agent not found - use direct Ollama call as fallback
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
            ):
                _ollama_timeout = max(_ollama_timeout, 1200.0)
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
            async with aiohttp.ClientSession() as session:
                # Mac Studio: используем локальные модели (Ollama и MLX)
                for ollama_url in ollama_urls:
                    try:
                        # Mac Studio: доступны лучшие модели
                        # Локальные модели (70b удалены)
                        # Ollama модели: glm-4.7-flash:q8_0, phi3.5:3.8b
                        if "localhost" in ollama_url or "127.0.0.1" in ollama_url:
                            # Mac Studio - лучшие модели
                            models_to_try = [
                                "victoria-wisdom-30b",
                                "glm-4.7-flash:q8_0",
                                "phi3.5:3.8b",
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
                                async with session.post(
                                    f"{ollama_url}/api/generate",
                                    json={"model": model_name, "prompt": prompt, "stream": False},
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
                            async with session.post(
                                f"{ollama_url}/api/generate",
                                json={"model": model_used, "prompt": prompt, "stream": False},
                                timeout=aiohttp.ClientTimeout(total=_ollama_timeout),
                            ) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    response = data.get("response", "")
                                    if response:
                                        logger.info(
                                            f"✅ [FALLBACK] Used Ollama at {ollama_url} with {model_used}"
                                        )
                                        return response
                            if resp.status == 200:
                                data = await resp.json()
                                response = data.get("response", "")
                                if response:
                                    logger.info(f"✅ [FALLBACK] Used Ollama at {ollama_url}")
                                    return response
                    except Exception as e:
                        logger.debug(f"Ollama at {ollama_url} failed: {e}")
                        continue
        except ImportError:
            logger.warning("aiohttp not available for Ollama fallback")
        except Exception as e:
            logger.warning(f"Ollama fallback failed: {e}")

        # Final fallback: smart_worker распознаёт "недоступн" и вызывает rule_executor
        return f"⚠️ Все источники недоступны. Запрос: {prompt[:100]}..."
    except Exception as exc:
        return f"❌ Ошибка связи с облаком: {exc}"


async def _get_knowledge_context(query: str) -> str:
    """Retrieve relevant knowledge nodes (GraphRAG) - знания корпорации + AI Research (Singularity 14.0)."""
    return await _get_knowledge_context_impl(query)


@profile_function("ai_core")
async def _get_knowledge_context_impl(query: str) -> str:
    """Implementation of knowledge retrieval."""
    if get_traffic_mirror:
        tm = get_traffic_mirror()
        await tm.mirror_request("ai_core", "_get_knowledge_context", query)
    try:
        # 1. Пробуем новый GraphRAG (Singularity 10.0)
        try:
            from app.graphrag.graphrag_service import get_graphrag_service

            graphrag = get_graphrag_service()
            graph_context = await graphrag.retrieve_graph_context(query)
            if graph_context:
                logger.info("🌐 [GRAPHRAG] Использован глобальный контекст и логические цепочки")
                return graph_context
        except Exception as ge:
            logger.debug(f"GraphRAG failed, falling back to standard RAG: {ge}")

        # 2. Fallback на стандартный векторный RAG
        embedding = await get_embedding(query)
        if not embedding:
            return ""
        pool = await _get_db_pool()
        if not pool:
            return ""

        async with pool.acquire() as conn:
            # [SINGULARITY 24.0] Hybrid RAG: Semantic + Keyword Search
            keywords = [w for w in query.lower().split() if len(w) > 3]
            keyword_filter = ""
            if keywords:
                # Формируем ILIKE условие для ключевых слов
                keyword_filter = (
                    "OR (" + " OR ".join([f"content ILIKE '%{k}%'" for k in keywords[:3]]) + ")"
                )

            # Поиск по трем направлениям: корпоративные знания, AI Research и логи обучения
            rows = await conn.fetch(
                f"""
                SELECT content, metadata, (1 - (embedding <=> $1::vector)) as similarity
                FROM knowledge_nodes
                WHERE (embedding IS NOT NULL OR content IS NOT NULL)
                AND (
                    domain_id = (SELECT id FROM domains WHERE name = 'AI Research' LIMIT 1)
                    OR domain_id = (SELECT id FROM domains WHERE name = 'victoria_tasks' LIMIT 1)
                    OR metadata->>'source' = 'external_docs_indexer'
                    OR source_ref = 'autonomous_worker'
                    OR metadata->>'type' = 'corporate_standard'
                )
                AND confidence_score >= 0.3
                AND ((1 - (embedding <=> $1::vector)) >= 0.5 {keyword_filter})
                ORDER BY similarity DESC NULLS LAST LIMIT 8
            """,
                str(embedding),
            )

            if not rows:
                return ""

            context = "\n📚 [KNOWLEDGE CONTEXT (AI Research & Corp)]:\n"
            for row in rows:
                if row["similarity"] >= 0.55:  # Понизили порог для лучшего охвата AI Research
                    meta = row["metadata"] or {}
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except:
                            meta = {}

                    source = meta.get("source", "unknown")
                    file_path = meta.get("file_path", "N/A")

                    if source == "external_docs_indexer":
                        context += f"\n[AI RESEARCH: {file_path}] (релевантность: {row['similarity']:.2f}):\n"
                    elif meta.get("type") == "corporate_system":
                        context += (
                            f"\n[КОРПОРАЦИЯ: СИСТЕМА] (релевантность: {row['similarity']:.2f}):\n"
                        )
                    else:
                        context += f"\n[ЗНАНИЕ] (релевантность: {row['similarity']:.2f}):\n"

                    context += f"{row['content'][:1200]}\n"
            return context
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
):
    """
    Hybrid Intelligence Orchestrator with Model Ensemble (Singularity 14.0).
    Victoria (Cloud) generates the plan, Local Worker (DeepSeek/Qwen) executes.
    Critial tasks are cross-verified by lfm2.5-thinking.
    """
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
):
    start_time = time.time()

    # [SINGULARITY 21.0] Enforce CoT for critical tasks
    if is_critical or category in ("reasoning", "vip"):
        require_cot = True
        if "ПОШАГОВО" not in prompt:
            prompt = f"### [SYSTEM: ENFORCED REASONING MODE]\nРЕШИ ЗАДАЧУ ПОШАГОВО (Chain-of-Thought).\n\n{prompt}"

    request_id = f"{expert_name}_{int(time.time())}"
    # Единый user_key/project_context для всех путей (в т.ч. вызов из execute_assignments без session_id)
    user_key = session_id or "orchestrator"
    project_context = os.getenv("MAIN_PROJECT", "atra-web-ide")
    user_part = prompt.split("Запрос:")[-1].strip() if "Запрос:" in prompt else prompt

    # [SINGULARITY 24.0] Lean Identity: Load SOUL.md and USER.md
    soul_context = ""
    user_context = ""
    try:
        # Пытаемся найти файлы в разных локациях (Docker vs Local)
        possible_paths = [
            os.path.dirname(__file__),
            os.path.join(os.getcwd(), "knowledge_os"),
            "/app/knowledge_os",
            os.getcwd(),  # Для вызова из корня
        ]
        for p in possible_paths:
            soul_p = os.path.join(p, "SOUL.md")
            user_p = os.path.join(p, "USER.md")
            if os.path.exists(soul_p) and not soul_context:
                with open(soul_p) as f:
                    soul_context = f"\n### 👩‍💼 MY SOUL (IDENTITY):\n{f.read()}\n"
            if os.path.exists(user_p) and not user_context:
                with open(user_p) as f:
                    user_context = f"\n### 👤 USER CONTEXT (BOSS):\n{f.read()}\n"
    except Exception as e:
        logger.debug(f"Lean Identity load failed: {e}")

    # [SINGULARITY 20.0] Wisdom Injection: Meta-Strategies from Knowledge Base
    meta_wisdom_context = ""
    mentorship_context = ""
    experience_context = ""
    constitution_context = ""
    cross_pollination_context = ""  # [SINGULARITY 24.0]
    try:
        # 0. Digital Constitution
        from digital_constitution import get_constitution_context

        constitution_context = get_constitution_context()

        pool = await _get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                # [SINGULARITY 24.0] Cross-Pollination Wisdom
                # Ищем инсайты из ДРУГИХ доменов, которые могут быть полезны
                try:
                    # Avoid circular import by using local import
                    from app.skill_registry import get_skill_registry

                    registry = get_skill_registry()

                    cross_nodes = await conn.fetch(
                        """
                        SELECT content, metadata->>'category' as cat FROM knowledge_nodes
                        WHERE is_verified = TRUE
                        AND metadata->>'category' != $1
                        AND confidence_score >= 0.8
                        ORDER BY created_at DESC LIMIT 2
                    """,
                        category or "general",
                    )
                    if cross_nodes:
                        cross_pollination_context = (
                            "\n### 🧬 CROSS-DOMAIN INSIGHTS (POLLINATION):\n"
                        )
                        for cn in cross_nodes:
                            cross_pollination_context += (
                                f"- [{cn['cat'].upper()}]: {cn['content'][:300]}\n"
                            )
                        logger.info(
                            f"🧬 [CROSS-POLLINATION] Injected {len(cross_nodes)} cross-domain insights"
                        )
                except Exception as cpe:
                    logger.debug(f"Cross-pollination failed: {cpe}")

                # 1. Meta-Strategies
                meta_nodes = await conn.fetch("""
                    SELECT content FROM knowledge_nodes
                    WHERE metadata->>'type' = 'meta_wisdom'
                    AND is_verified = TRUE
                    ORDER BY created_at DESC LIMIT 3
                """)
                if meta_nodes:
                    meta_wisdom_context = "\n### 🏛 CORPORATE META-STRATEGIES (WISDOM):\n"
                    for node in meta_nodes:
                        meta_wisdom_context += f"- {node['content']}\n"
                    logger.info(f"🏛 [WISDOM INJECTION] Injected {len(meta_nodes)} meta-strategies")

                # 2. Mentorship Notes for current expert
                mentorship_nodes = await conn.fetch(
                    """
                    SELECT content FROM knowledge_nodes
                    WHERE metadata->>'type' = 'mentorship_note'
                    AND metadata->>'target_expert' = $1
                    ORDER BY created_at DESC LIMIT 2
                """,
                    expert_name,
                )
                if mentorship_nodes:
                    mentorship_context = f"\n### 🎓 MENTORSHIP FEEDBACK FOR {expert_name}:\n"
                    for node in mentorship_nodes:
                        mentorship_context += f"- {node['content']}\n"
                    logger.info(
                        f"🎓 [MENTORSHIP INJECTION] Injected {len(mentorship_nodes)} notes for {expert_name}"
                    )

                # 3. [SINGULARITY 20.0] Voice of Experience: Predictive Warnings
                try:
                    from experience_retriever import get_experience_context

                    experience_context = await get_experience_context(user_part, expert_name)
                    if experience_context:
                        logger.info(
                            f"🧠 [VOICE OF EXPERIENCE] Injected proactive warnings for {expert_name}"
                        )
                except Exception as ee:
                    logger.debug(f"⚠️ [VOICE OF EXPERIENCE] Error: {ee}")
    except Exception as we:
        logger.debug(f"⚠️ [WISDOM/MENTORSHIP INJECTION] Error: {we}")

    # --- MODEL ENSEMBLE LOGIC (Phase 2.7) ---
    async def _verify_and_refine(initial_prompt: str, initial_response: str, depth: int = 0) -> str:
        """Кросс-верификация ответа быстрой моделью-критиком (lfm2.5-thinking)."""
        if depth >= 1:  # Ограничиваем рекурсию одной попыткой исправления
            return initial_response

        logger.info(f"🧠 [ENSEMBLE] Запуск верификации для {expert_name} (глубина {depth})")

        # [SINGULARITY 24.0] Empathetic Verification: Check against SOUL.md
        verify_prompt = f"""Ты - AI-аудитор и хранитель 'Души' корпорации.
Проверь ответ на наличие критических ошибок, галлюцинаций и соответствие стандартам SOUL.md.

СТАНДАРТЫ SOUL.md:
- Тон: Профессиональный, умный, но живой (не как робот).
- Идентичность: Виктория, Team Lead (я, мы).
- Принципы: First Principles, Root Cause.

ЗАПРОС ПОЛЬЗОВАТЕЛЯ: {initial_prompt}
ОТВЕТ ДЛЯ ПРОВЕРКИ: {initial_response}

Если всё верно и тон соответствует Виктории, напиши 'OK'.
Если есть ошибка или ответ слишком 'сухой/роботизированный', опиши проблему и предложи исправление в стиле Виктории."""

        # Используем lfm2.5-thinking как самого быстрого и логичного критика
        try:
            if router:
                # Сингулярность 10.0: Увеличиваем таймаут для критика до 600с
                verify_result = await router.run_local_llm(
                    verify_prompt, category="general", model_hint="lfm2.5-thinking:1.2b"
                )
                verify_text = (
                    verify_result[0] if isinstance(verify_result, tuple) else verify_result
                )

                if verify_text and "OK" not in verify_text.upper()[:10]:
                    logger.warning(
                        f"⚠️ [ENSEMBLE] Критик нашел проблему (логика или тон): {verify_text[:100]}..."
                    )

                    refine_prompt = f"""Исправь ответ, учитывая замечания критика по логике или тону (стиль Виктории).
ЗАМЕЧАНИЯ КРИТИКА: {verify_text}
ИСХОДНЫЙ ЗАПРОС: {initial_prompt}
ИСПРАВЬ И ВЕРНИ ПОЛНЫЙ ОТВЕТ В СТИЛЕ ВИКТОРИИ:"""

                    refined_result = await router.run_local_llm(refine_prompt, category="coding")
                    return (
                        refined_result[0] if isinstance(refined_result, tuple) else refined_result
                    )
            return initial_response
        except Exception as e:
            logger.error(f"❌ [ENSEMBLE] Ошибка верификации: {e}")
            return initial_response

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

            result = await run_brainstorming(user_part, knowledge_context)
            return f"✅ Коллективное обсуждение завершено.\n\n### 🏛 Финальный дизайн\n{result['design']}\n\n### 📋 План реализации\n{result['plan']}\n\nПолный лог обсуждения сохранен в docs/plans/."

        # [SINGULARITY 10.0+] Multi-Agent Debate for critical tasks
        if is_critical and get_multi_agent_debate:
            logger.info("⚖️ [CRITICAL] Starting Multi-Agent Debate for critical task...")
            debate = get_multi_agent_debate()
            debate_result = await debate.run_debate(prompt)
            if debate_result and debate_result.final_decision:
                logger.info("✅ [DEBATE COMPLETE] Critical decision reached.")
                return debate_result.final_decision

        from anomaly_detector import get_anomaly_detector

        anomaly_detector = get_anomaly_detector()
        should_block, alert = await anomaly_detector.analyze_request(
            prompt,
            identifier=request_id,
            metadata={"expert_name": expert_name, "category": category},
        )
        if should_block:
            logger.warning(
                f"🚨 [ANOMALY DETECTOR] Запрос заблокирован: {alert.description if alert else 'unknown'}"
            )
            return "⚠️ Запрос отклонен системой безопасности."

        # Проверка на блокировку
        if anomaly_detector.is_blocked(request_id):
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
        # Запускаем параллельно: проверку кэша и получение контекста знаний
        tasks = []
        if cache and not images:
            tasks.append(cache.get_cached_response(user_part, expert_name))
        else:
            tasks.append(asyncio.sleep(0, result=None))

        tasks.append(_get_knowledge_context(user_part))

        return await asyncio.gather(*tasks)

    # 1.1. Проверка кэша и контекста (Singularity 10.0+)
    cached_response, kb_context_rag = await get_cache_and_context()

    if cached_response:
        logger.info(f"🎯 [CACHE HIT] Found similar query for expert {expert_name}")
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
        else (LocalAIRouter() if LocalAIRouter else None)
    )
    distiller = KnowledgeDistiller() if KnowledgeDistiller else None
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

    # [SINGULARITY 24.0] Predictive Context Prefetching
    # Проверяем, нет ли заранее подгруженных SOP в Redis
    try:
        import hashlib

        from app.redis_manager import RedisManager

        redis_manager = RedisManager()
        prefetch_key = f"prefetch:{hashlib.md5(user_part.encode()).hexdigest()}"
        prefetched_sop = await redis_manager.get_cache(prefetch_key)
        if prefetched_sop:
            kb_context = f"\n### ПРЕДЗАГРУЖЕННЫЕ СТАНДАРТЫ (SOP):\n{prefetched_sop}\n---\n"
            logger.info("🔮 [PREFETCH] Injected prefetched context from Redis")
    except Exception as pe:
        logger.debug(f"Prefetch injection failed: {pe}")

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
        or meta_wisdom_context
        or mentorship_context
        or experience_context
        or constitution_context
        or soul_context
        or user_context
    ):
        # [SINGULARITY 14.2] Use ContextSwapper for kb_context
        swapper = ContextSwapper()
        full_context = f"{constitution_context}\n{soul_context}\n{user_context}\n{cross_pollination_context}\n{meta_wisdom_context}\n{mentorship_context}\n{experience_context}\n{kb_context}"
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

    # 3. Hybrid Strategy: Manager-Worker Pattern (Strategist vs Executor)
    # If the task is coding or audit, we use Strategist (Wisdom) to plan and Executor (Qwen3) to execute

    # [SINGULARITY 20.0] Load hybrid models from .env
    strategist_model = os.getenv("VICTORIA_STRATEGIST_MODEL", "victoria-wisdom-30b")
    executor_model = os.getenv("VICTORIA_EXECUTOR_MODEL", "victoria-wisdom-30b")

    # Track token savings
    tokens_saved = 0

    if is_coding_task and not is_critical:
        logger.info(
            f"👩‍💼 [STRATEGIST MODE] {strategist_model} is planning for {executor_model}..."
        )
        # [SINGULARITY 10.0+] Episodic Memory (User preferences)
        episodic_context = ""
        if get_episodic_memory_manager:
            em = get_episodic_memory_manager()
            episodic_context = await em.get_episodes(user_key, project_context)
            if episodic_context:
                knowledge_context = f"{episodic_context}\n\n{knowledge_context}"

        # [SINGULARITY 13.0] Self-Distillation Rules
        distilled_rules = ""
        if get_distillation_engine:
            de = get_distillation_engine()
            distilled_rules = await de.get_active_rules()
            if distilled_rules:
                knowledge_context = f"{distilled_rules}\n\n{knowledge_context}"

        # Phase 1: Strategist generates a TECHNICAL SPECIFICATION (MLX call)
        spec_prompt = f"""
        Вы - ВИКТОРИЯ, Главный Стратег (Wisdom Era). Составьте краткое ТЕХНИЧЕСКОЕ ЗАДАНИЕ (ТЗ) для младшего разработчика
        на основе запроса пользователя. Укажите только ЧТО сделать, без написания самого кода.

        {style_modifier}
        {emotion_modifier}

        ЗАПРОС: {user_part}
        """

        # [SINGULARITY 10.0+] Personality Adaptation (Anthropic pattern)
        if get_personality_manager:
            pm = get_personality_manager()
            spec_prompt = pm.adapt_prompt(user_part, spec_prompt)

        # Используем Strategist (Wisdom) на MLX
        spec = None
        if router:
            # Форсируем использование Wisdom на MLX для планирования
            spec_result = await router.run_local_llm(
                spec_prompt, category="reasoning", model_hint=strategist_model
            )
            spec = spec_result[0] if isinstance(spec_result, tuple) else spec_result

        # Fallback to cloud if strategist failed
        if not spec or spec.startswith(("❌", "⚠️")):
            logger.warning("⚠️ [STRATEGIST FAILED] Falling back to cloud for planning...")
            spec = await _run_cloud_agent_async(spec_prompt)

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
                if distiller and hasattr(distiller, "get_relevant_examples"):
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

                worker_prompt = f"{examples}\n\n{style_modifier}\n{emotion_modifier}\n\nТЗ ОТ СТРАТЕГА ({strategist_model}):\n{spec}\n\nВЫПОЛНИТЕ ЗАДАНИЕ:"
                logger.info(f"👷 [EXECUTOR START] {executor_model} executing TS locally...")

                # Используем Executor (Qwen3) на Ollama
                try:
                    if router:
                        local_result = await router.run_local_llm(
                            worker_prompt, category="coding", model_hint=executor_model
                        )
                    else:
                        local_result = None
                except Exception as e:
                    logger.warning(f"⚠️ [EXECUTOR FAILED] {e}")
                    # [SINGULARITY 24.0] Self-Healing: Check for context overflow
                    if "context" in str(e).lower() or "too long" in str(e).lower():
                        logger.info("🩹 [SELF-HEALING] Context overflow detected. Compacting...")
                        # Агрессивное сжатие: берем только ТЗ и последние факты
                        worker_prompt = f"### [SELF-HEALING MODE: COMPACTED CONTEXT]\n\nТЗ ОТ СТРАТЕГА:\n{spec[:2000]}\n\nВЫПОЛНИТЕ ЗАДАНИЕ:"
                        try:
                            local_result = await router.run_local_llm(
                                worker_prompt, category="coding", model_hint=executor_model
                            )
                        except Exception as e2:
                            logger.error(f"❌ [SELF-HEALING FAILED] Retry also failed: {e2}")
                            local_result = None
                    else:
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
                        local_resp = None  # Force cloud fallback
                    elif recommendation == "retry_local":
                        logger.info("🔄 [QUALITY GATE] Retrying with local model...")
                        # Можно попробовать еще раз с другим промптом
                        # Пока просто перенаправляем в облако
                        local_resp = None

            # Safety check for local response (дополнительная проверка)
            if local_resp and SafetyChecker:
                checker = SafetyChecker()
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

                    local_resp = None  # Force cloud fallback

            # Fallback to cloud if local model failed or safety check failed
            if not local_resp:
                logger.warning(
                    "⚠️ [LOCAL FAILED] Local model returned None, falling back to cloud..."
                )
                # Use cloud for execution if local failed
                local_resp = await _run_cloud_agent_async(worker_prompt)
                if local_resp and not local_resp.startswith(("❌", "⚠️")):
                    logger.info("✅ [CLOUD FALLBACK] Cloud executed the task successfully")
                    if cache:
                        await cache.save_to_cache(user_part, local_resp, expert_name)
                    return local_resp

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
                should_run_audit = use_audit or (
                    force_audit and (is_critical or is_critical_domain)
                )

                audit_result = "APPROVED"  # По умолчанию считаем результат одобренным
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
                            audit_prompt, category="reasoning", model_hint=strategist_model
                        )
                        audit_result = audit_res[0] if isinstance(audit_res, tuple) else audit_res
                    else:
                        audit_result = await _run_cloud_agent_async(audit_prompt)

                    if audit_result and "APPROVED" not in audit_result.upper():
                        logger.warning(
                            f"⚠️ [AUDIT REJECTED] Victoria found issues in {expert_name}'s work."
                        )
                    else:
                        logger.info(f"✅ [AUDIT APPROVED] Victoria approved {expert_name}'s work.")

            if audit_result and "APPROVED" in audit_result.upper():
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

                if EmotionDetector and emotion_result:
                    metadata_dict["detected_emotion"] = emotion_result.detected_emotion
                    metadata_dict["emotion_confidence"] = emotion_result.confidence
                    metadata_dict["tone_used"] = emotion_result.tone
                    metadata_dict["detail_level"] = emotion_result.detail_level

                    # Логируем эмоцию в emotion_logs
                    try:
                        from token_logger import log_ai_interaction

                        interaction_log_id = await log_ai_interaction(
                            prompt=user_part,
                            response=local_resp[:2000],  # Ограничиваем длину для производительности
                            expert_name=expert_name,
                            model_type="local",
                            source="ai_core",
                            metadata=metadata_dict,
                        )

                        if interaction_log_id:
                            detector = EmotionDetector()
                            feedback_score = (
                                None  # Будет обновлен позже, когда пользователь даст feedback
                            )
                            await detector.log_emotion(
                                interaction_log_id, emotion_result, feedback_score
                            )
                    except Exception as e:
                        logger.debug(f"⚠️ [EMOTION DETECTOR] Error logging emotion: {e}")

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
                        await distiller.save_correction(
                            expert_id,
                            category or "coding",
                            user_part,
                            local_resp,
                            "...",
                            audit_result,
                        )

                final_prompt = f"ПЛАН ИСПРАВЛЕНИЯ ОТ ТИМЛИДА:\n{audit_result}\n\nИСПРАВЬТЕ КОД:"
                final_result = await router.run_local_llm(final_prompt, category="coding")
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
                timeout=600.0 if (is_vip or category in ("reasoning", "vip")) else 120.0,
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
                            router.run_local_llm, prompt, category=category, images=images
                        )
                    else:
                        result = await router.run_local_llm(
                            prompt, category=category, images=images
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
                    timeout=600.0,  # Увеличено до 600s для тяжелых моделей
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
                        prompt, category=category, images=images
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
                    prompt, category=category, images=images, is_vip=is_vip
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
            checker = SafetyChecker()
            if checker.should_reroute_to_cloud(
                local_resp, response_type="code" if category == "coding" else "text"
            ):
                logger.warning("🛡️ [SAFETY CHECK] Local response failed, using cloud")
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

            return local_resp

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

    # 6. Full Cloud Call (for Strategic / Architecture tasks)
    knowledge_context = await _get_knowledge_context(user_part)

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

    # Умное сокращение контекста перед отправкой в облако (агрессивное сжатие)
    # Predictive Compression: проверяем предсжатый контекст (Singularity 14.0)
    compressed_prompt = full_prompt
    latency_before_compression = time.time()
    latency_reduction = 0.0

    if ContextAnalyzer and len(full_prompt) > 2000:
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
                    full_prompt, user_part, max_length=2000
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
                full_prompt, user_part, max_length=2000
            )
            tokens_saved = (len(full_prompt) - len(compressed_prompt)) // 4
            logger.info(
                f"📉 [CONTEXT COMPRESSION] Compressed from {len(full_prompt)} to {len(compressed_prompt)} chars (~{tokens_saved} tokens saved)"
            )
    elif ContextCompressor:
        # Используем агрессивное сжатие
        compressed_prompt = await ContextCompressor.compress_smart(
            full_prompt, user_part, max_length=2000, aggressive=True
        )
        if len(compressed_prompt) < len(full_prompt):
            tokens_saved = (len(full_prompt) - len(compressed_prompt)) // 4
            logger.info(
                f"📉 [CONTEXT COMPRESSION] Compressed from {len(full_prompt)} to {len(compressed_prompt)} chars (~{tokens_saved} tokens saved)"
            )
        else:
            compressed_prompt = ContextCompressor.compress_all(full_prompt)

    cloud_start_time = time.time()
    response = await _run_cloud_agent_async(compressed_prompt)
    cloud_latency_ms = (time.time() - cloud_start_time) * 1000

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
        logger.info("🛠️ [TOOL CREATOR] Attempting to create a missing tool to fix the failure...")
        creator = get_autonomous_tool_creator()
        success = await creator.create_tool_on_the_fly(response, user_part)
        if success:
            logger.info("✅ [TOOL CREATOR] New tool created. Retrying task...")
            # Retry once with the new tool
            response = await _run_cloud_agent_async(compressed_prompt)

    # Offline fallback
    if response and (response.startswith("❌") or response.startswith("⚠️")) and router:
        logger.warning("🛡️ [BUNKER MODE] Cloud failed, switching to Local.")
        return await router.run_local_llm(prompt)

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
            for kw in ["всегда", "никогда", "предпочитаю", "мне нравится", "используй только"]
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

    return response


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
    if not ShadowExecutionManager:
        return

    try:
        pool = await _get_db_pool()
        if not pool:
            return

        # 1. Check for active shadow mutations for this expert
        async with pool.acquire() as conn:
            expert_id = await _get_expert_id(expert_name)
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
                            router = LocalAIRouter()
                            res = await router.run_local_llm(
                                shadow_prompt, category=category or "general"
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
                        logger.warning(
                            f"⚠️ [SHADOW] ShadowEvaluator not found, skipping evaluation for {mutation_id}"
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


# Sync wrapper implementation would go here (omitted for brevity)
