"""
[SINGULARITY CORE] AI Agent Coordination Module.
Handles caching, routing, knowledge retrieval (RAG), and consensus across agents.
Optimized for Hybrid Intelligence (Cloud Architect + Local Worker).
"""

import asyncio
import os
import logging
import getpass
import json
import time
from typing import Optional, List, Dict, Any

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
    async def get_embedding(text: str) -> Optional[List[float]]: return None

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
        def compress_all(prompt: str) -> str: return prompt

try:
    from safety_checker import SafetyChecker  # type: ignore
except ImportError:
    SafetyChecker = None  # type: ignore

try:
    from veronica_web_researcher import VeronicaWebResearcher  # type: ignore
except ImportError:
    VeronicaWebResearcher = None  # type: ignore

try:
    from optimizers import PromptOptimizer, EmbeddingCache, PredictiveCache, FrugalPrompt, BETokenManager, get_betoken_manager  # type: ignore
except ImportError:
    PromptOptimizer = None  # type: ignore
    EmbeddingCache = None  # type: ignore
    PredictiveCache = None  # type: ignore
    FrugalPrompt = None  # type: ignore
    BETokenManager = None  # type: ignore
    get_betoken_manager = None  # type: ignore

try:
    from parallel_request_processor import ParallelRequestProcessor, RequestSource, get_parallel_processor  # type: ignore
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
    from query_orchestrator import QueryOrchestrator, QueryType  # type: ignore
    from prompt_templates import get_prompt_template, format_prompt  # type: ignore
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
    from circuit_breaker import get_circuit_breaker, CircuitBreakerOpenError  # type: ignore
except ImportError:
    get_circuit_breaker = None  # type: ignore
    CircuitBreakerOpenError = Exception

try:
    from disaster_recovery import get_disaster_recovery, SystemMode  # type: ignore
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

logger = logging.getLogger(__name__)

# Global user identification for conditional logic
USER_NAME = getpass.getuser()

# --- PERFORMANCE BOOST: DB CONNECTION POOLING ---
_DB_POOL = None

async def _get_db_pool():
    """Lazy initialization of the PostgreSQL connection pool."""
    global _DB_POOL
    if _DB_POOL is None and asyncpg:
        try:
            default_url = os.getenv('DATABASE_URL') or 'postgresql://admin:secret@localhost:5432/knowledge_os'
            db_url = os.getenv('DATABASE_URL_LOCAL', default_url)
            _DB_POOL = await asyncpg.create_pool(
                db_url, 
                min_size=1, 
                max_size=5,  # Уменьшено для предотвращения перегрузки БД
                max_inactive_connection_lifetime=300
            )
        except Exception as exc:
            logger.error("❌ Failed to create DB pool: %s", exc)
    return _DB_POOL

async def _run_cloud_agent_async(prompt: str):
    """Приоритет: локальные модели (Ollama/MLX) → cursor-agent. Локальные модели корпорации используются первыми."""
    # ПРИОРИТЕТ 1: локальные модели (Ollama/MLX) — политика корпорации
    if LocalAIRouter:
        try:
            router = LocalAIRouter()
            result = await router.run_local_llm(prompt, category="general")
            if isinstance(result, tuple):
                response, _ = result
            else:
                response = result
            if response and len(response) > 10:
                logger.info("✅ [LOCAL FIRST] Использована локальная модель (Ollama/MLX) вместо облака")
                return response
        except Exception as e:
            logger.warning(f"⚠️ [LOCAL FIRST] Локальный роутер недоступен: {e}, пробуем cursor-agent")
    
    # ПРИОРИТЕТ 2: cursor-agent (облако) — только если локальные модели недоступны
    try:
        env = os.environ.copy()
        agent_path = 'cursor-agent'
        process = await asyncio.create_subprocess_exec(
            agent_path, '--print', prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        try:
            # Уменьшаем таймаут до 30 секунд для быстрого fallback
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            if process.returncode == 0:
                return stdout.decode().strip()
            return f"⚠️ Ошибка облачного мозга: {stderr.decode()[:100]}"
        except asyncio.TimeoutError:
            process.kill()
            logger.warning("⏱️ [CLOUD TIMEOUT] Облачный запрос таймаутился (30s), переключаюсь на локальные модели")
            # При таймауте облака пытаемся использовать локальные модели
            if LocalAIRouter:
                try:
                    router = LocalAIRouter()
                    # Быстрый fallback на локальные модели с таймаутом 15 секунд
                    result = await asyncio.wait_for(
                        router.run_local_llm(prompt, category="general"),
                        timeout=15
                    )
                    if isinstance(result, tuple):
                        response, _ = result
                    else:
                        response = result
                    if response and len(response) > 10:
                        logger.info("✅ [TIMEOUT FALLBACK] Использованы локальные модели после таймаута облака")
                        return response
                except asyncio.TimeoutError:
                    logger.warning("⚠️ [TIMEOUT FALLBACK] Локальные модели также таймаутятся (15s)")
                except Exception as e:
                    logger.warning(f"⚠️ [TIMEOUT FALLBACK] Локальные модели также недоступны: {e}")
            return "⌛ Облачный запрос занял слишком много времени. Локальные модели также недоступны."
    except FileNotFoundError:
        # 🍎 ПРИОРИТЕТ 1: Попробовать MLX (Apple Neural Engine) для снижения нагрузки на MacBook
        try:
            from knowledge_os.app.mlx_router import get_mlx_router, is_mlx_available
            if is_mlx_available():
                mlx_router = get_mlx_router()
                logger.info("🍎 [MLX] Пробуем использовать Apple MLX (Neural Engine) для снижения нагрузки")
                mlx_response = await mlx_router.generate_response(
                    prompt=prompt,
                    max_tokens=512,
                    temperature=0.7
                )
                if mlx_response and len(mlx_response) > 10:
                    logger.info("✅ [MLX] Использован Apple MLX (Neural Engine) - нагрузка на MacBook снижена")
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
            async with aiohttp.ClientSession() as session:
                # Try server first (phi3 available), then MacBook if accessible
                # Note: localhost on server = server itself, not MacBook
                # MacBook would need to be accessible via network IP (not implemented yet)
                for ollama_url in ["http://localhost:11434"]:
                    try:
                        # MacBook: use better models (deepseek-r1, qwen2.5-coder)
                        # Server: use lightweight models (phi3, phi4) for low RAM
                        if "localhost" in ollama_url or "127.0.0.1" in ollama_url:
                            # MacBook - лучшие модели
                            # MLX модели (Mac Studio): qwen2.5-coder:32b, deepseek-r1-distill-llama:70b
                            # Ollama модели: glm-4.7-flash:q8_0, phi3.5:3.8b
                            models_to_try = ["deepseek-r1-distill-llama:70b", "qwen2.5-coder:32b", "glm-4.7-flash:q8_0", "phi3.5:3.8b"]
                        else:
                            # Server - легкие модели (1.9GB RAM)
                            models_to_try = ["phi3:latest", "phi3", "phi4:latest", "phi4", "tinyllama", "gemma:2b"]
                        
                        response = None
                        model_used = None
                        
                        for model_name in models_to_try:
                            try:
                                async with session.post(
                                    f"{ollama_url}/api/generate",
                                    json={
                                        "model": model_name,
                                        "prompt": prompt,
                                        "stream": False
                                    },
                                    timeout=aiohttp.ClientTimeout(total=120)
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
                            logger.info(f"✅ [FALLBACK] Used Ollama at {ollama_url} with {model_used}")
                            return response
                        else:
                            async with session.post(
                                f"{ollama_url}/api/generate",
                                json={
                                    "model": model_used,
                                    "prompt": prompt,
                                    "stream": False
                                },
                                timeout=aiohttp.ClientTimeout(total=120)
                            ) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    response = data.get("response", "")
                                    if response:
                                        logger.info(f"✅ [FALLBACK] Used Ollama at {ollama_url} with {model_used}")
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
        
        # Final fallback: return a helpful message
        return f"⚠️ Все источники недоступны. Запрос: {prompt[:100]}..."
    except Exception as exc:
        return f"❌ Ошибка связи с облаком: {exc}"

async def _get_knowledge_context(query: str) -> str:
    """Retrieve relevant knowledge nodes (RAG) - включает знания корпорации."""
    try:
        embedding = await get_embedding(query)
        if not embedding: return ""
        pool = await _get_db_pool()
        if not pool: return ""
        async with pool.acquire() as conn:
            # Ищем релевантные знания, включая знания корпорации
            rows = await conn.fetch("""
                SELECT content, metadata, (1 - (embedding <=> $1::vector)) as similarity
                FROM knowledge_nodes
                WHERE embedding IS NOT NULL
                AND confidence_score >= 0.3
                ORDER BY similarity DESC LIMIT 5
            """, embedding)
        if not rows: return ""
        context = "\n📚 [KNOWLEDGE CONTEXT]:\n"
        for row in rows:
            if row['similarity'] >= 0.6:  # Понизили порог для лучшего покрытия
                metadata = row['metadata'] or {}
                source = metadata.get('source', 'unknown')
                knowledge_type = metadata.get('type', 'general')
                
                # Добавляем информацию о типе знания
                if source == 'corporation_knowledge_system':
                    context += f"\n[КОРПОРАЦИЯ: {knowledge_type}] (релевантность: {row['similarity']:.2f}):\n"
                else:
                    context += f"\n[ЗНАНИЕ] (релевантность: {row['similarity']:.2f}):\n"
                context += f"{row['content']}\n"
        return context
    except Exception as exc:
        logger.error("Knowledge retrieval error: %s", exc)
        return ""

async def run_smart_agent_async(
    prompt: str,
    expert_name: str = "Виктория",
    category: Optional[str] = None,
    require_cot: bool = False,
    is_critical: bool = False,
    images: Optional[list] = None,
    session_id: Optional[str] = None
):
    """
    Hybrid Intelligence Orchestrator.
    Victoria (Cloud) generates the plan, Local Worker (DeepSeek/Qwen) executes.
    """
    import time
    start_time = time.time()
    request_id = f"{expert_name}_{int(time.time())}"
    
    # 0. Anomaly Detection: проверка запроса на аномалии
    try:
        from anomaly_detector import get_anomaly_detector
        anomaly_detector = get_anomaly_detector()
        should_block, alert = await anomaly_detector.analyze_request(
            prompt,
            identifier=request_id,
            metadata={"expert_name": expert_name, "category": category}
        )
        if should_block:
            logger.warning(f"🚨 [ANOMALY DETECTOR] Запрос заблокирован: {alert.description if alert else 'unknown'}")
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
    router = LocalAIRouter() if LocalAIRouter else None
    distiller = KnowledgeDistiller() if KnowledgeDistiller else None
    qa = QualityAssurance(min_quality_threshold=0.7) if QualityAssurance else None
    quality_gate = QualityGate(qa) if QualityGate and qa else None
    parallel_processor = ParallelProcessor(max_concurrent=3) if ParallelProcessor else None
    
    # ML Router v2 для предсказания оптимального роутинга (Singularity 8.0)
    ml_router_v2 = get_ml_router_v2() if get_ml_router_v2 else None
    predicted_route = None
    route_confidence = 0.0
    
    # Circuit breakers для критических компонентов
    db_breaker = get_circuit_breaker("database", failure_threshold=5, recovery_timeout=60) if get_circuit_breaker else None
    local_breaker = get_circuit_breaker("local_models", failure_threshold=3, recovery_timeout=30) if get_circuit_breaker else None
    cloud_breaker = get_circuit_breaker("cloud", failure_threshold=3, recovery_timeout=30) if get_circuit_breaker else None
    
    user_part = prompt.split("Запрос:")[-1].strip() if "Запрос:" in prompt else prompt
    
    # Проверка на запрос стратегии: автоматический запуск Discovery → MASTER_PLAN → декомпозиция
    is_strategy_request = False
    if QueryOrchestrator and not session_id:
        try:
            temp_orch = QueryOrchestrator()
            query_type = temp_orch.classify_query(user_part)
            is_strategy_request = query_type == QueryType.STRATEGY
        except Exception:
            pass
    
    # Если это запрос на стратегию и нет session_id, создаем сессию и запускаем Discovery
    if is_strategy_request and not session_id:
        try:
            from strategy_session_manager import StrategySessionManager
            from strategy_discovery import StrategyDiscovery
            
            session_manager = StrategySessionManager()
            new_session_id = session_manager.create_session(
                title=user_part[:100],  # Первые 100 символов как название
                description=user_part
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
                    cursor.execute("SELECT question_text FROM strategy_questions WHERE id = ?", (qid,))
                    row = cursor.fetchone()
                    if row:
                        questions_text_parts.append(f"❓ Вопрос {i+1}: {row['question_text']}")
                conn.close()
                
                questions_text = "\n".join(questions_text_parts)
                return f"📋 Discovery фаза начата для сессии {new_session_id}.\n\n{questions_text}\n\nПожалуйста, ответьте на вопросы для продолжения планирования."
            
            # Если вопросов нет, сразу переходим к планированию
            if discovery.is_ready_for_planning(new_session_id):
                from master_plan_generator import MasterPlanGenerator
                from plan_decomposer import PlanDecomposer
                
                generator = MasterPlanGenerator(session_manager=session_manager, query_orch=temp_orch)
                plan_id = await generator.generate_master_plan(new_session_id)
                
                if plan_id:
                    decomposer = PlanDecomposer(session_manager=session_manager, query_orch=temp_orch)
                    await decomposer.decompose_master_plan(new_session_id)
                    
                    return f"✅ MASTER_PLAN создан и декомпозирован для сессии {new_session_id}. План ID: {plan_id}"
        except Exception as e:
            logger.debug(f"⚠️ [ITERATIVE PLANNING] Ошибка автоматического планирования: {e}")
            # Продолжаем обычный путь
    
    # Обработка изображений (мультимодальность)
    if images and get_vision_processor:
        vision_processor = get_vision_processor()
        image_analysis = await vision_processor.describe_image(image_base64=images[0] if isinstance(images[0], str) else None)
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
                logger.info(f"💰 [FRUGAL PROMPT] Сжато с {len(user_part)} до {len(frugal_compressed)} символов")
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
            logger.info(f"✅ [QUALITY GATE] Оптимизация применена: {len(original_user_part)} -> {len(user_part)} символов")
        else:
            logger.warning("⚠️ [QUALITY GATE] Prompt optimization too aggressive, using original")
            user_part = original_user_part

    # 1.5. Tacit Knowledge Extractor: получаем стилевой профиль пользователя (Singularity 9.0)
    style_profile = None
    style_modifier = ""
    user_identifier = session_id or "default_user"  # Используем session_id как user_identifier или дефолт
    style_similarity_score = 0.0
    
    # 1.6. Emotional Response Modulation: детектируем эмоцию пользователя (Singularity 9.0)
    emotion_result = None
    emotion_modifier = ""
    
    if EmotionDetector:
        try:
            detector = EmotionDetector()
            emotion_result = await detector.detect_emotion_with_history(user_part, user_identifier)
            
            if emotion_result and emotion_result.confidence >= 0.5:  # MIN_EMOTION_CONFIDENCE = 0.5
                emotion_modifier = detector.create_style_modifier(emotion_result)
                logger.info(f"😊 [EMOTION DETECTOR] Detected emotion: {emotion_result.detected_emotion} (confidence: {emotion_result.confidence:.2f})")
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
- Конвенция именования: {prefs.get('naming_convention', 'snake_case')}
- Обработка ошибок: {prefs.get('error_handling', 'defensive_with_exceptions')}
- Стиль тестирования: {prefs.get('testing_style', 'tdd_with_pytest')}
- Стиль документации: {prefs.get('documentation_style', 'detailed_docstrings')}
- Структура кода: {prefs.get('code_structure', 'functional')}
- Именование переменных: {prefs.get('variable_naming', 'descriptive_names')}
- Стиль функций: {prefs.get('function_style', 'simple')}

ВАЖНО: Генерируй код строго в соответствии с этими предпочтениями.
"""
                logger.info(f"🎨 [TACIT KNOWLEDGE] Style profile loaded for user {user_identifier}")
        except Exception as e:
            logger.debug(f"⚠️ [TACIT KNOWLEDGE] Error loading style profile: {e}")
            style_profile = None

    # 1.6. Определяем тип задачи (до проверки кэша, так как используется в Tacit Knowledge)
    is_coding_task = any(kw in user_part.lower() for kw in ["код", "программируй", "рефакторинг", "тест", "аудит", "проверь"])

    # 2. Cache Check (улучшенный) - через circuit breaker
    if cache and not images:
        try:
            if db_breaker:
                cached = await db_breaker.call(cache.get_cached_response, user_part, expert_name)
            else:
                cached = await cache.get_cached_response(user_part, expert_name)
            
            if cached:
                logger.info("🚀 [CACHE HIT] %s", expert_name)
                
                # Предсказательное кэширование: пред-генерируем ответы на вероятные запросы
                if PredictiveCache:
                    pred_cache = PredictiveCache(cache)
                    await pred_cache.predict_and_cache(user_part, expert_name)
                
                return cached
        except CircuitBreakerOpenError as e:
            logger.warning(f"⚠️ [CIRCUIT BREAKER] Cache недоступен: {e}")
            # Продолжаем без кэша
        except Exception as e:
            logger.debug(f"Cache check failed: {e}")
            # Продолжаем без кэша

    # 3. Hybrid Strategy: Manager-Worker Pattern
    # If the task is coding or audit, we use Victoria to plan and Local to execute
    
    # Track token savings
    tokens_saved = 0
    
    if is_coding_task and not is_critical:
        logger.info("👩‍💼 [ORCHESTRATOR MODE] Victoria is planning for Local Worker...")
        
        # Phase 1: Victoria generates a TECHNICAL SPECIFICATION (short cloud call)
        spec_prompt = f"""
        Вы - Виктория, Team Lead. Составьте краткое ТЕХНИЧЕСКОЕ ЗАДАНИЕ (ТЗ) для младшего разработчика 
        на основе запроса пользователя. Укажите только ЧТО сделать, без написания самого кода.
        
        {style_modifier}
        {emotion_modifier}
        
        ЗАПРОС: {user_part}
        """
        spec = await _run_cloud_agent_async(spec_prompt)
        
        if spec and not spec.startswith(('❌', '⚠️')):
            # Phase 2: Local Worker executes the spec
            # Проверяем доступность локальных моделей через disaster recovery
            if disaster_recovery and not disaster_recovery.can_use_local_models():
                logger.warning("⚠️ [DISASTER RECOVERY] Локальные модели недоступны, используем облако")
                local_result = None
            else:
                # Inject few-shot examples from distillation engine
                examples = ""
                if distiller:
                    try:
                        if db_breaker:
                            examples = await db_breaker.call(distiller.get_relevant_examples, user_part, category or "coding")
                        else:
                            examples = await distiller.get_relevant_examples(user_part, category or "coding")
                    except CircuitBreakerOpenError:
                        logger.warning("⚠️ [CIRCUIT BREAKER] Distillation engine недоступен, продолжаем без примеров")
                        examples = ""
                
                worker_prompt = f"{examples}\n\n{style_modifier}\n{emotion_modifier}\n\nТЗ ОТ ТИМЛИДА:\n{spec}\n\nВЫПОЛНИТЕ ЗАДАНИЕ:"
                logger.info("👷 [WORKER START] Executing TS locally...")
                
                # Логируем использование ML vs эвристики
                if router and hasattr(router, 'ml_model') and router.ml_model:
                    logger.info("🤖 [ML ROUTER] Using ML-based routing")
                else:
                    logger.info("📊 [HEURISTIC ROUTER] Using heuristic routing")
                
                # Используем circuit breaker для локальных моделей
                try:
                    if local_breaker and router:
                        local_result = await local_breaker.call(router.run_local_llm, worker_prompt, category="coding")
                    elif router:
                        local_result = await router.run_local_llm(worker_prompt, category="coding")
                    else:
                        local_result = None
                except CircuitBreakerOpenError as e:
                    logger.warning(f"⚠️ [CIRCUIT BREAKER] Локальные модели недоступны: {e}")
                    local_result = None
            local_resp, routing_source = local_result if isinstance(local_result, tuple) else (local_result, None)
            
            # Quality Assurance: проверка качества ответа
            if local_resp and qa:
                is_acceptable, metrics, recommendation = await qa.validate_response(
                    local_resp, user_part, response_type="code", source="local"
                )
                
                if not is_acceptable:
                    logger.warning(f"⚠️ [QUALITY CHECK] Local response quality {metrics.overall_score:.2f} below threshold")
                    
                    # Собираем feedback о низком качестве
                    if get_feedback_collector:
                        collector = await get_feedback_collector()
                        await collector.collect_implicit_feedback(
                            query=user_part,
                            response=local_resp,
                            routing_source=routing_source or "local",
                            rerouted_to_cloud=True,
                            reroute_reason="low_quality",
                            quality_score=metrics.overall_score
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
                    logger.warning("🛡️ [SAFETY CHECK] Local response failed safety check, rerouting to cloud")
                    
                    # Собираем feedback о failed safety check
                    if get_feedback_collector:
                        collector = await get_feedback_collector()
                        await collector.collect_implicit_feedback(
                            query=user_part,
                            response=local_resp,
                            routing_source=routing_source or "local",
                            rerouted_to_cloud=True,
                            reroute_reason="safety_check_failed"
                        )
                    
                    local_resp = None  # Force cloud fallback
            
            # Fallback to cloud if local model failed or safety check failed
            if not local_resp:
                logger.warning("⚠️ [LOCAL FAILED] Local model returned None, falling back to cloud...")
                # Use cloud for execution if local failed
                local_resp = await _run_cloud_agent_async(worker_prompt)
                if local_resp and not local_resp.startswith(('❌', '⚠️')):
                    logger.info("✅ [CLOUD FALLBACK] Cloud executed the task successfully")
                    if cache: await cache.save_to_cache(user_part, local_resp, expert_name)
                    return local_resp
            
            if local_resp:
                # Сохраняем метрики результата для ML-обучения
                quality_metrics = None
                if qa:
                    _, quality_metrics, _ = await qa.validate_response(
                        local_resp, user_part, response_type="code", source="local"
                    )
                
                # Phase 3: Victoria validates the result (Short audit)
                audit_prompt = f"""
                Вы - Виктория, Team Lead. Проверьте код, написанный разработчиком. 
                Если в коде есть критические ошибки, напишите ПЛАН ИСПРАВЛЕНИЯ. 
                Если код отличный, напишите 'APPROVED'.
                
                КОД РАЗРАБОТЧИКА:
                {local_resp}
                """
                audit_result = await _run_cloud_agent_async(audit_prompt)
                
            if audit_result and "APPROVED" in audit_result:
                # Estimate token savings (local execution vs full cloud)
                estimated_cloud_tokens = len(user_part) // 4 + len(local_resp) // 4
                estimated_local_tokens = len(spec) // 4 + len(audit_result) // 4  # Only planning + audit
                tokens_saved = estimated_cloud_tokens - estimated_local_tokens
                logger.info(f"✅ [AUDIT PASSED] Code approved by Victoria. 💰 Tokens saved: ~{tokens_saved}")
                
                # Tacit Knowledge: вычисляем style_similarity_score (Singularity 9.0)
                if TacitKnowledgeMiner and style_profile and local_resp:
                    try:
                        miner = TacitKnowledgeMiner()
                        style_similarity_score = await miner.calculate_style_similarity(local_resp, user_identifier)
                        logger.info(f"🎨 [TACIT KNOWLEDGE] Style similarity: {style_similarity_score:.2f}")
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
                                user_part, local_resp, expert_name,
                                routing_source=final_routing_source,
                                performance_score=1.0,  # Approved = high score
                                tokens_saved=tokens_saved
                            )
                        else:
                            await cache.save_to_cache(
                                user_part, local_resp, expert_name,
                                routing_source=final_routing_source,
                                performance_score=1.0,  # Approved = high score
                                tokens_saved=tokens_saved
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
                            quality_score=quality_metrics.overall_score if quality_metrics else None,
                            success=True,
                            features={
                                "expert_name": expert_name,
                                "final_approved": True
                            }
                        )
                    except CircuitBreakerOpenError:
                        logger.warning("⚠️ [CIRCUIT BREAKER] Не удалось сохранить в кэш, продолжаем без сохранения")
                elif cache and disaster_recovery:
                    logger.debug("⚠️ [DISASTER RECOVERY] БД недоступна для записи, пропускаем сохранение в кэш")
                
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
                        features={
                            "audit_result": "approved",
                            "expert_name": expert_name
                            }
                        )
                
                # Логируем style_similarity_score и emotion в metadata (Singularity 9.0)
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
                            metadata=metadata_dict
                        )
                        
                        if interaction_log_id:
                            detector = EmotionDetector()
                            feedback_score = None  # Будет обновлен позже, когда пользователь даст feedback
                            await detector.log_emotion(interaction_log_id, emotion_result, feedback_score)
                    except Exception as e:
                        logger.debug(f"⚠️ [EMOTION DETECTOR] Error logging emotion: {e}")
                
                return local_resp
            else:
                # FEEDBACK LOOP: Send back to local with audit notes
                logger.warning("🔄 [REVISION NEEDED] Victoria found issues. Retrying locally with feedback...")
                if distiller:
                    # Save the error for learning
                    expert_id = await _get_expert_id(expert_name)
                    if expert_id:  # Only save if expert_id is valid
                        await distiller.save_correction(
                            expert_id, category or "coding", user_part, local_resp, "...", audit_result
                        )
                
                final_prompt = f"ПЛАН ИСПРАВЛЕНИЯ ОТ ТИМЛИДА:\n{audit_result}\n\nИСПРАВЬТЕ КОД:"
                final_result = await router.run_local_llm(final_prompt, category="coding")
                final_resp, _ = final_result if isinstance(final_result, tuple) else (final_result, None)
                if not final_resp:
                    logger.warning("⚠️ [REVISION FAILED] Local model failed on revision, returning original")
                    return local_resp
                return final_resp  # Return revised version

    # 4. Web-Enabled Local Route (Вероника с веб-поиском)
    # Проверяем, нужен ли веб-поиск (запросы о текущих событиях, новостях, трендах)
    needs_web_search = any(kw in user_part.lower() for kw in [
        "новости", "тренды", "сейчас", "текущие", "актуальные", 
        "последние", "2025", "2024", "сегодня", "недавно", "latest", "recent"
    ])
    
    use_local_route = bool(router and (images or router.should_use_local(prompt, category)) or needs_web_search)
    if use_local_route:
        logger.info("🏠 [ROUTE] Выбран локальный маршрут (Ollama/MLX): images=%s, should_use_local=%s, needs_web=%s",
                    bool(images), bool(router and router.should_use_local(prompt, category)), needs_web_search)
    else:
        logger.info("☁️ [ROUTE] Выбран облачный маршрут (сначала попробуем локальные внутри _run_cloud_agent_async): category=%s", category)
    
    if router and (images or router.should_use_local(prompt, category)) or needs_web_search:
        # Если нужен веб-поиск, используем Веронику
        if needs_web_search and VeronicaWebResearcher:
            logger.info("🌐 [VERONICA WEB] Запрос требует веб-поиска, используем Веронику")
            veronica = VeronicaWebResearcher()
            result = await veronica.research_and_analyze(
                user_part,
                category=category or "research",
                use_web=True
            )
            
            if result and result.get('analysis'):
                    logger.info(f"✅ [VERONICA WEB] Ответ получен (0 токенов использовано!)")
                    if cache:
                        await cache.save_to_cache(
                            user_part, result['analysis'], expert_name,
                            routing_source="veronica_web",
                            tokens_saved=len(result['analysis']) // 4,  # Экономия от облака
                            performance_score=0.9
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
                                tokens_saved=len(result['analysis']) // 4,
                                success=True,
                                features={
                                    "expert_name": expert_name,
                                    "web_search": True
                                }
                            )
                        except Exception as e:
                            logger.debug(f"Failed to collect veronica routing data: {e}")
                    
                    return result['analysis']
        
        # Параллельная обработка: локальные модели и облако одновременно
        if ParallelRequestProcessor and get_parallel_processor and router:
            logger.info("⚡ [PARALLEL] Параллельная обработка: локальные модели и облако")
            parallel_processor = get_parallel_processor(max_concurrent=3)
            
            # Создаем источники для параллельной обработки
            sources = []
            
            # Локальные модели (приоритет 1 - быстрее)
            async def try_local():
                if disaster_recovery and not disaster_recovery.can_use_local_models():
                    return None
                try:
                    if local_breaker:
                        result = await local_breaker.call(router.run_local_llm, prompt, category=category, images=images)
                    else:
                        result = await router.run_local_llm(prompt, category=category, images=images)
                    if isinstance(result, tuple):
                        return result[0]
                    return result
                except Exception as e:
                    logger.debug(f"Local model failed in parallel: {e}")
                    return None
            
            sources.append(RequestSource(
                name="local",
                handler=try_local,
                priority=1,
                timeout=30.0
            ))
            
            # Облако (приоритет 2 - медленнее, но качественнее)
            async def try_cloud():
                try:
                    if cloud_breaker:
                        return await cloud_breaker.call(_run_cloud_agent_async, prompt)
                    else:
                        return await _run_cloud_agent_async(prompt)
                except Exception as e:
                    logger.debug(f"Cloud failed in parallel: {e}")
                    return None
            
            sources.append(RequestSource(
                name="cloud",
                handler=try_cloud,
                priority=2,
                timeout=60.0
            ))
            
            # Параллельно обрабатываем источники
            response_source_name, response = await parallel_processor.process_parallel_sources(sources)
            
            if response:
                routing_source = f"{response_source_name}_parallel" if response_source_name else "parallel"
                local_resp = response
                logger.info(f"✅ [PARALLEL] Получен ответ от {routing_source}")
            else:
                # Если параллельная обработка не дала результата, пробуем последовательно
                logger.warning("⚠️ [PARALLEL] Параллельная обработка не дала результата, пробуем последовательно")
                if router:
                    logger.info("🏠 [LOCAL ROUTE] %s", expert_name)
                    local_result = await router.run_local_llm(prompt, category=category, images=images)
                    local_resp, routing_source = local_result if isinstance(local_result, tuple) else (local_result, None)
                else:
                    logger.warning("⚠️ [FALLBACK] Local router unavailable, using cloud")
                    local_resp = await _run_cloud_agent_async(prompt)
                    routing_source = "cloud_fallback"
        else:
            # Обычный локальный маршрут (без параллельной обработки)
            if router:
                logger.info("🏠 [LOCAL ROUTE] %s", expert_name)
                local_result = await router.run_local_llm(prompt, category=category, images=images)
                local_resp, routing_source = local_result if isinstance(local_result, tuple) else (local_result, None)
            else:
                # Fallback на облако, если локальный роутер недоступен
                logger.warning("⚠️ [FALLBACK] Local router unavailable, using cloud")
                local_resp = await _run_cloud_agent_async(prompt)
                routing_source = "cloud_fallback"
        
        # Safety check for direct local responses
        if local_resp and SafetyChecker:
            checker = SafetyChecker()
            if checker.should_reroute_to_cloud(local_resp, response_type="code" if category == "coding" else "text"):
                logger.warning("🛡️ [SAFETY CHECK] Local response failed, using cloud")
                local_resp = None
        
        if local_resp:
            # Estimate savings for direct local usage
            estimated_cloud_tokens = len(prompt) // 4 + len(local_resp) // 4
            logger.info(f"💰 [TOKEN SAVINGS] Used local model, saved ~{estimated_cloud_tokens} tokens")
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
                    user_part, local_resp, expert_name,
                    routing_source=final_routing_source,
                    tokens_saved=estimated_cloud_tokens,
                    performance_score=performance_score
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
                        features={
                            "expert_name": expert_name,
                            "direct_local": True
                        }
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
            logger.info(f"🎯 [QUERY ORCHESTRATOR] Запрос нормализован: тип={normalized_query.query_type.value}, роль={optimized_role}")
        except Exception as e:
            logger.debug(f"⚠️ [QUERY ORCHESTRATOR] Ошибка нормализации запроса: {e}, используем старый путь")
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
                normalized_query=normalized_query
            )
            
            # Оптимизируем контекст (сжатие до 70% окна)
            prompt_context = query_orchestrator.optimize_context(prompt_context, max_length=2000, max_window_percent=0.7)
            
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
                constraints=", ".join(normalized_query.constraints) if normalized_query.constraints else "Нет",
                preferences=", ".join(normalized_query.preferences) if normalized_query.preferences else "Нет"
            )
            
            logger.info(f"✅ [QUERY ORCHESTRATOR] Промпт собран через шаблон роли: длина={len(full_prompt)}, роль={optimized_role}")
        except Exception as e:
            logger.debug(f"⚠️ [QUERY ORCHESTRATOR] Ошибка сборки промпта: {e}, используем старый путь")
            full_prompt = (knowledge_context + "\n" + prompt) if knowledge_context else prompt
    else:
        # Старый путь: просто объединяем промпт с контекстом
        full_prompt = (knowledge_context + "\n" + prompt) if knowledge_context else prompt
    
    # Умное сокращение контекста перед отправкой в облако (агрессивное сжатие)
    # Predictive Compression: проверяем предсжатый контекст (Singularity 9.0)
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
                latency_reduction = ((latency_before_compression - latency_after_compression) / latency_before_compression) if latency_before_compression > 0 else 0.0
                tokens_saved = (len(full_prompt) - len(compressed_prompt)) // 4
                logger.info(f"🚀 [PREDICTIVE COMPRESSION] Using precompressed context: {len(compressed_prompt)} chars (~{tokens_saved} tokens saved, latency ↓ {latency_reduction:.1%})")
            else:
                # Обычное сжатие, если предсжатый контекст не найден
                analyzer = ContextAnalyzer(relevance_threshold=0.65)
                compressed_prompt = await analyzer.compress_context(full_prompt, user_part, max_length=2000)
                tokens_saved = (len(full_prompt) - len(compressed_prompt)) // 4
                logger.info(f"📉 [CONTEXT COMPRESSION] Compressed from {len(full_prompt)} to {len(compressed_prompt)} chars (~{tokens_saved} tokens saved)")
        except Exception as e:
            logger.debug(f"⚠️ [PREDICTIVE COMPRESSION] Error checking precompressed context: {e}")
            # Fallback к обычному сжатию
            analyzer = ContextAnalyzer(relevance_threshold=0.65)
            compressed_prompt = await analyzer.compress_context(full_prompt, user_part, max_length=2000)
            tokens_saved = (len(full_prompt) - len(compressed_prompt)) // 4
            logger.info(f"📉 [CONTEXT COMPRESSION] Compressed from {len(full_prompt)} to {len(compressed_prompt)} chars (~{tokens_saved} tokens saved)")
    elif ContextCompressor:
        # Используем агрессивное сжатие
        compressed_prompt = await ContextCompressor.compress_smart(full_prompt, user_part, max_length=2000, aggressive=True)
        if len(compressed_prompt) < len(full_prompt):
            tokens_saved = (len(full_prompt) - len(compressed_prompt)) // 4
            logger.info(f"📉 [CONTEXT COMPRESSION] Compressed from {len(full_prompt)} to {len(compressed_prompt)} chars (~{tokens_saved} tokens saved)")
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
                    "prompt_compressed": len(compressed_prompt) < len(full_prompt)
                }
            )
            logger.debug("✅ [ML DATA] Saved cloud routing decision")
        except Exception as e:
            logger.debug(f"⚠️ [ML DATA] Failed to collect cloud routing data: {e}")

    # Offline fallback
    if response and (response.startswith('❌') or response.startswith('⚠️')) and router:
        logger.warning("🛡️ [BUNKER MODE] Cloud failed, switching to Local.")
        return await router.run_local_llm(prompt)
    
    # Дополнение ответа внешними данными (Singularity 8.0)
    if response and not response.startswith(('⚠️', '❌')):
        try:
            from external_api_integration import get_external_api_integration
            external_api = get_external_api_integration()
            enhanced_response = await external_api.enhance_response_with_external_data(user_part, response)
            if enhanced_response and len(enhanced_response) > len(response):
                response = enhanced_response
                logger.info("🌐 [EXTERNAL API] Ответ дополнен внешними данными")
        except Exception as e:
            logger.debug(f"⚠️ [EXTERNAL API] Ошибка дополнения ответа: {e}")

    # Определяем финальный response если еще не определен
    if 'response' not in locals():
        response = local_resp if 'local_resp' in locals() else None
    
    if cache and response and not response.startswith(('⚠️', '❌')):
        await cache.save_to_cache(user_part, response, expert_name)
    
    # Сохранение контекста сессии (Singularity 8.0)
    if get_session_context_manager and response and not response.startswith(('⚠️', '❌')):
        try:
            # Получаем user_id из request_id (если доступен) или используем дефолтный
            user_id = request_id.split('_')[0] if '_' in request_id else "default"
            context_manager = get_session_context_manager()
            await context_manager.save_to_context(
                user_id=user_id,
                expert_name=expert_name,
                query=user_part,
                response=response
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
                if 'routing_source' in locals() or 'routing_source' in globals():
                    routing_src = locals().get('routing_source') or globals().get('routing_source')
                elif 'local_resp' in locals() and locals().get('local_resp'):
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
            # Формируем metadata для логирования (Singularity 9.0 - Predictive Compression)
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
                metadata=metadata_for_logging if metadata_for_logging else None
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
            await metrics_collector.collect_tokens_per_second(
                estimated_tokens, duration, "cloud"
            )
    except Exception as e:
        logger.debug(f"Metrics collection failed: {e}")

    return response

async def _get_expert_id(name: str) -> str:
    """Helper to get expert UUID from DB."""
    pool = await _get_db_pool()
    if not pool: return None
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT id FROM experts WHERE name = $1", name)

# Sync wrapper implementation would go here (omitted for brevity)
