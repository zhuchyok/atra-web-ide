"""
Chat Router - SSE стриминг для AI чата (Singularity 9.0)
Интеграция с Streaming и Emotional Modulation
Улучшенная обработка ошибок и кэширование
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, AsyncGenerator
import json
import logging
import os
import asyncio

from app.config import get_settings
from app.services.victoria import VictoriaClient, get_victoria_client
from app.services.mlx import MLXClient, get_mlx_client
from app.services.ollama import OllamaClient, get_ollama_client
from app.services.knowledge_os import KnowledgeOSClient, get_knowledge_os_client
from app.services.streaming import StreamingProcessor, create_sse_event
from app.services.emotions import detect_emotion, get_adapted_prompt, Emotion
from app.services.cache import get_cache, cache_key
from app.services.query_classifier import classify_query, get_template_response, analyze_complexity
from app.services.rag_light import get_rag_light_service
from app.services.plan_cache import get_plan_cache_service, PlanCacheService
from app.services.conversation_context import get_conversation_context_manager
from app.metrics.agent_suggestions import agent_suggestion_metrics, AgentSuggestionMetric
from app.metrics.prometheus_metrics import (
    metrics as prometheus_metrics,
    PLAN_REQUESTS,
    PLAN_DURATION,
    PLAN_STEPS_COUNT,
)
from app.services.concurrency_limiter import (
    acquire_victoria_slot,
    release_victoria_slot,
    with_victoria_slot,
)
import httpx
import time
import uuid

logger = logging.getLogger(__name__)
router = APIRouter()

# Минимальная длина ответа, при которой проверяем повторения (символы)
_REPEAT_CHECK_MIN_LEN = 200
# Максимум повторов одной и той же фразы — после этого обрезаем
_MAX_REPEATS_ALLOWED = 2
# Длина фрагмента для поиска повтора (одно предложение, напр. «Виктория: Я - виктория, ассистент...»)
_REPEAT_PATTERN_LEN = 100


def _truncate_repeated_response(content: str) -> str:
    """
    Обрезает ответ, если модель зациклилась на одной фразе (например «Виктория: Я - виктория, ассистент...»).
    Оставляет не более _MAX_REPEATS_ALLOWED повторов и добавляет пометку.
    """
    if not content or len(content) < _REPEAT_CHECK_MIN_LEN:
        return content
    text = content.strip()
    pattern_len = min(_REPEAT_PATTERN_LEN, len(text) // 2)
    if pattern_len < 50:
        return content
    sample = text[:pattern_len]
    # Считаем, сколько раз подряд в начале текста повторяется тот же блок
    start = 0
    repeat_count = 0
    while start + pattern_len <= len(text):
        if text[start : start + pattern_len] == sample:
            repeat_count += 1
            start += pattern_len
        else:
            break
    if repeat_count <= _MAX_REPEATS_ALLOWED:
        return content
    cut = pattern_len * _MAX_REPEATS_ALLOWED
    space_at = text.rfind(" ", 0, min(cut + 1, len(text)))
    if space_at > cut // 2:
        cut = space_at
    result = text[:cut].strip()
    if result and result[-1] not in ".!?":
        result += "."
    return result + "\n\n(повторение в ответе модели сокращено)"


async def _log_chat_to_knowledge_os(prompt: str, response: str, expert_name: Optional[str] = None) -> None:
    """Fire-and-forget: логирует чат в interaction_logs (Singularity 9.0) через Knowledge OS API."""
    try:
        settings = get_settings()
        url = f"{settings.knowledge_os_api_url.rstrip('/')}/api/log_interaction"
        logger.info("[LOG_INTERACTION] url=%s prompt_len=%s response_len=%s expert=%s", url, len(prompt), len(response), expert_name)
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                url,
                json={
                    "prompt": prompt[:10000],
                    "response": response[:20000],
                    "expert_name": expert_name,
                    "source": "web_ide",
                },
            )
        if r.status_code != 200:
            logger.warning("[LOG_INTERACTION] status=%s body=%s", r.status_code, (r.text or "")[:200])
    except Exception as e:
        logger.error("[LOG_INTERACTION] error=%s", e, exc_info=True)


class ChatMessage(BaseModel):
    """Сообщение в чат"""
    content: str = Field(..., min_length=1, max_length=10000)
    expert_name: Optional[str] = Field(default=None, max_length=100)
    model: Optional[str] = Field(default=None, max_length=100)
    use_victoria: bool = True
    mode: Optional[str] = Field(default="agent", description="agent | plan | ask — как в Cursor")
    user_id: Optional[str] = Field(default=None, max_length=128, description="Для A/B тестов")
    session_id: Optional[str] = Field(default=None, max_length=128, description="Фаза 4.2: контекст диалога (multi-turn)")


# Простые сообщения для которых не нужен агент Victoria (быстрый путь через MLX)
SIMPLE_PATTERNS = [
    "привет", "hello", "hi", "здравствуй", "добрый день", "добрый вечер",
    "как дела", "как ты", "что умеешь", "кто ты", "помоги", "расскажи",
    "спасибо", "thanks", "пока", "bye", "good", "объясни", "explain",
    "напиши", "write", "покажи", "show", "код", "code",
    "функци", "function", "класс", "class", "python", "javascript", "rust",
    "что такое", "what is", "как работает", "how does", "зачем", "почему",
    "где", "when", "какой", "which", "сколько"
]

# Паттерны для Victoria Agent (сложные задачи, корпорация, сервера)
VICTORIA_PATTERNS = [
    "файл на сервере", "ssh", "подключись", "запусти на", "выполни команду",
    "создай проект", "разверни", "deploy", "docker", "контейнер",
    "корпорац", "сервер", "статус", "проверь", "victoria", "виктория",
    "агент", "задач", "mac studio", "макстудио", "mlx"
]


def is_simple_message(content: str) -> bool:
    """Проверить, является ли сообщение простым (не требует агента)"""
    lower = content.lower().strip()
    
    # Если явно нужен Victoria Agent
    for pattern in VICTORIA_PATTERNS:
        if pattern in lower:
            return False
    
    # Большинство сообщений - простые (быстрый путь)
    if len(lower) < 200:
        return True
    
    # Длинные сообщения с простыми паттернами тоже простые
    for pattern in SIMPLE_PATTERNS:
        if pattern in lower:
            return True
    
    return False


def _select_model_for_chat(content: str, expert_name: Optional[str] = None) -> str:
    """
    Автоматический выбор модели на основе содержания сообщения и эксперта
    
    Использует все 8 моделей Mac Studio M4 Max:
    - complex/enterprise → command-r-plus:104b (~65GB)
    - reasoning → deepseek-r1-distill-llama:70b (~40GB)
    - complex → llama3.3:70b (~40GB)
    - coding (high quality) → qwen2.5-coder:32b (~20GB)
    - fast/general → phi3.5:3.8b (~2.5GB)
    - fast (lightweight) → phi3:mini-4k (~2GB)
    - fast/default → qwen2.5:3b (~2GB)
    - fast (ultra-lightweight) → phi3:mini-4k (~2.3GB) (tinyllama исключена - только для коммуникации агентов)
    """
    content_lower = content.lower()
    
    # Сложные задачи, корпоративные, RAG, enterprise
    if any(word in content_lower for word in ["сложн", "корпорац", "rag", "enterprise", "критичн", "важн", "стратег"]):
        return "command-r-plus:104b"  # Максимальная мощность
    
    # Reasoning, планирование, логика, анализ
    if any(word in content_lower for word in ["подумай", "логика", "планир", "reasoning", "анализ", "объясни", "почему"]):
        return "deepseek-r1-distill-llama:70b"  # Reasoning
    
    # Максимальное качество, сложные задачи
    if any(word in content_lower for word in ["качеств", "лучш", "оптимальн", "максимальн", "детальн"]):
        return "llama3.3:70b"  # Максимальное качество
    
    # Код, программирование, рефакторинг (high quality)
    if any(word in content_lower for word in ["код", "программир", "рефактор", "функци", "класс", "python", "javascript", "typescript", "алгоритм"]):
        return "qwen2.5-coder:32b"  # Качественный код
    
    # Быстрые задачи, общие (medium)
    if len(content) > 200 or any(word in content_lower for word in ["расскажи", "объясни", "описа"]):
        return "phi3.5:3.8b"  # Fast, general
    
    # Быстрые ответы, легкие задачи (lightweight)
    if len(content) < 200:
        return "phi3:mini-4k"  # Fast, lightweight
    
    # Очень быстрые (ultra-lightweight) - короткие сообщения
    if len(content) < 100:
        return "phi3.5:3.8b"  # Быстрая модель (tinyllama исключена - только для коммуникации агентов)
    
    # По умолчанию - быстрая модель
    return "qwen2.5:3b"  # Fast, default


async def _get_available_model(ideal_model: str, mlx: MLXClient) -> str:
    """
    Проверяет доступность модели и возвращает fallback если нужно
    
    Args:
        ideal_model: Идеальная модель для задачи
        mlx: MLXClient для проверки доступности
    
    Returns:
        Доступная модель (идеальная или fallback)
    """
    # Маппинг идеальных моделей на возможные варианты имен в MLX
    model_variants = {
        "command-r-plus:104b": ["command-r-plus", "command-r-plus:104b", "command-r", "c4ai-command-r-plus"],
        "deepseek-r1-distill-llama:70b": ["deepseek-r1-distill-llama", "deepseek-r1-distill", "deepseek-r1:70b", "deepseek-r1"],
        "llama3.3:70b": ["llama3.3", "llama3.3:70b", "llama-3.3", "llama"],
        "qwen2.5-coder:32b": ["qwen2.5-coder:32b", "qwen2.5-coder-32b", "qwen2.5-coder", "qwen-coder-32"],
        "phi3.5:3.8b": ["phi3.5", "phi3.5:3.8b", "phi-3.5", "phi3.5-mini"],
        "phi3:mini-4k": ["phi3:mini", "phi3-mini", "phi3:mini-4k", "phi-3-mini"],
        "qwen2.5:3b": ["qwen2.5:3b", "qwen2.5-3b", "qwen2.5", "qwen-3b"],
        # "tinyllama:1.1b-chat": ["tinyllama", "tinyllama:1.1b", "tinyllama-1.1b", "tiny-llama"]  # Исключена - только для коммуникации агентов
    }
    
    # Fallback цепочки для каждой категории (модели Mac Studio)
    # Используем только РЕАЛЬНО существующие модели из Ollama
    # Ollama: qwq:32b, qwen2.5-coder:32b, glm-4.7-flash:q8_0, llava:7b, phi3.5:3.8b, moondream:latest, tinyllama:1.1b-chat
    fallback_chains = {
        "command-r-plus:104b": ["llama3.3:70b", "qwen2.5-coder:32b", "phi3.5:3.8b"],
        "deepseek-r1-distill-llama:70b": ["qwq:32b", "qwen2.5-coder:32b", "phi3.5:3.8b"],
        "llama3.3:70b": ["deepseek-r1-distill-llama:70b", "qwen2.5-coder:32b", "phi3.5:3.8b"],
        "qwen2.5-coder:32b": ["qwq:32b", "phi3.5:3.8b", "tinyllama:1.1b-chat"],
        "qwq:32b": ["qwen2.5-coder:32b", "glm-4.7-flash:q8_0", "phi3.5:3.8b"],
        "glm-4.7-flash:q8_0": ["qwq:32b", "qwen2.5-coder:32b", "phi3.5:3.8b"],
        "phi3.5:3.8b": ["qwen2.5-coder:32b", "tinyllama:1.1b-chat"],
        "phi3:mini-4k": ["phi3.5:3.8b", "tinyllama:1.1b-chat"],
        "qwen2.5:3b": ["phi3.5:3.8b", "tinyllama:1.1b-chat"],
    }
    
    # Проверяем идеальную модель
    try:
        # Проверяем доступность через MLX health
        mlx_health = await mlx.health()
        available_models = mlx_health.get("available_models", [])
        models = [{"name": m} for m in available_models] if available_models else []
        available_names = [m.get("name", "") for m in models]
        
        # Проверяем точное совпадение
        if ideal_model in available_names:
            logger.info(f"✅ Используем идеальную модель: {ideal_model}")
            return ideal_model
        
        # Проверяем варианты имен для идеальной модели
        variants = model_variants.get(ideal_model, [ideal_model])
        for variant in variants:
            # Точное совпадение варианта
            if variant in available_names:
                logger.info(f"✅ Используем вариант модели: {variant} (вместо {ideal_model})")
                return variant
            # Частичное совпадение
            for name in available_names:
                variant_base = variant.split(":")[0].split("-")[0]
                name_base = name.split(":")[0].split("-")[0]
                if variant_base in name_base or name_base in variant_base:
                    if len(variant_base) > 3:  # Избегаем слишком общих совпадений
                        logger.info(f"✅ Используем похожую модель: {name} (вместо {ideal_model})")
                        return name
        
        # Используем fallback цепочку
        # Используем только реально существующие модели из Ollama
        fallbacks = fallback_chains.get(ideal_model, ["qwen2.5-coder:32b", "phi3.5:3.8b", "tinyllama:1.1b-chat"])
        for fallback in fallbacks:
            if fallback in available_names:
                logger.info(f"⚠️ Используем fallback: {fallback} (вместо {ideal_model})")
                return fallback
            # Проверяем частичное совпадение для fallback
            for name in available_names:
                fallback_base = fallback.split(":")[0].split("-")[0]
                name_base = name.split(":")[0].split("-")[0]
                if fallback_base in name_base or name_base in fallback_base:
                    if len(fallback_base) > 3:
                        logger.info(f"⚠️ Используем похожий fallback: {name} (вместо {ideal_model})")
                        return name
        
        # Последний резерв - первая доступная модель (кроме embeddings и vision)
        for name in available_names:
            if "embed" not in name.lower() and "dream" not in name.lower():
                logger.warning(f"⚠️ Используем первую доступную модель: {name} (вместо {ideal_model})")
                return name
        
        # Если ничего не найдено, возвращаем идеальную модель (пусть MLX вернет ошибку)
        logger.warning(f"⚠️ Не удалось найти доступную модель, используем {ideal_model}")
        return ideal_model
        
    except Exception as e:
        logger.error(f"Ошибка проверки доступности моделей: {e}")
        # В случае ошибки возвращаем идеальную модель
        return ideal_model


async def _generate_via_mlx_or_ollama(
    full_prompt: str,
    ideal_model: str,
    mlx: MLXClient,
    ollama: OllamaClient,
    system: str = "Ты - полезный ИИ-ассистент корпорации ATRA. Отвечай кратко на русском.",
) -> tuple:
    """
    Цепочка выбора: MLX → Ollama → (None = переход на Victoria).
    Возвращает (content, source) или (None, None).
    """
    # 1) MLX
    mlx_health = await mlx.health()
    if mlx_health.get("status") in ("healthy", "degraded"):
        try:
            result = await mlx.generate(
                prompt=full_prompt,
                system=system,
                max_tokens=512,
                model=ideal_model,
            )
            if result and isinstance(result, dict) and result.get("response"):
                return (result["response"].strip(), "mlx")
        except Exception as e:
            logger.debug(f"MLX generate failed: {e}")
    # 2) Ollama
    ollama_health = await ollama.health()
    if ollama_health.get("status") == "healthy":
        try:
            result = await ollama.generate(
                prompt=full_prompt,
                model=ideal_model,
                system=system,
                stream=False,
            )
            if result and isinstance(result, dict):
                text = result.get("response") or result.get("message", {}).get("content") or ""
                if isinstance(text, list):
                    text = "".join(c.get("text", "") for c in text if isinstance(c, dict))
                if text and "error" not in result:
                    return (text.strip(), "ollama")
        except Exception as e:
            logger.debug(f"Ollama generate failed: {e}")
    return (None, None)


class ChatResponse(BaseModel):
    """Ответ от чата"""
    content: str
    expert_name: Optional[str] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None


class PlanRequest(BaseModel):
    """Запрос плана у Виктории"""
    goal: str = Field(..., min_length=1, max_length=10000)


class PlanResponse(BaseModel):
    """Ответ с планом"""
    plan: str
    status: str = "success"


async def sse_generator(
    message: ChatMessage,
    victoria: VictoriaClient,
    mlx: MLXClient,
    ollama: OllamaClient,
    knowledge_os: KnowledgeOSClient,
    plan_cache: PlanCacheService = None,
) -> AsyncGenerator[str, None]:
    """
    Генератор SSE событий (Singularity 9.0)
    
    Yields:
        SSE события в формате: data: {...}\n\n
    """
    # Singularity v9.0: Детекция эмоций
    emotion, confidence = detect_emotion(message.content)
    emotion_data = {
        'emotion': emotion.value,
        'confidence': round(confidence, 2)
    }
    
    # Singularity v5.0: Streaming processor
    processor = StreamingProcessor(buffer_size=3, min_delay=0.03, max_delay=0.1)
    
    def _flush_sse():
        """SSE comment — заставляет прокси/сервер отправить буфер клиенту."""
        return ": \n\n"

    # Correlation ID для трассировки (чат → Victoria → Veronica). ARCHITECTURE_IMPROVEMENTS_ANALYSIS.
    correlation_id = str(uuid.uuid4())
    logger.info("[CHAT] correlation_id=%s goal_preview=%s", correlation_id[:8], (message.content or "")[:50])

    # Фаза 4, Неделя 2: контекст диалога (multi-turn)
    session_id = getattr(message, "session_id", None) or getattr(message, "user_id", None)
    context_prefix = ""
    recent_messages: list = []
    if session_id:
        settings_ctx = get_settings()
        if getattr(settings_ctx, "conversation_context_enabled", True):
            ctx_mgr = get_conversation_context_manager()
            recent_messages = await ctx_mgr.get_recent(session_id, last_n=10)
            context_prefix = ctx_mgr.build_context_prefix(recent_messages)
    response_parts = []
    current_prompt = (context_prefix + message.content) if context_prefix else message.content

    async def _save_context_if_needed():
        if not session_id:
            return
        full_response = "".join(response_parts).strip()
        if not full_response:
            return
        try:
            ctx_mgr = get_conversation_context_manager()
            await ctx_mgr.append(session_id, "user", message.content)
            await ctx_mgr.append(session_id, "assistant", full_response)
        except Exception as e:
            logger.debug("Conversation context save failed: %s", e)

    try:
        # Отправляем начало с информацией об эмоции
        start_event = {
            'type': 'start',
            'expert': message.expert_name,
            'emotion': emotion_data
        }
        yield f"data: {json.dumps(start_event)}\n\n"
        yield _flush_sse()

        # Режим агента: шаги (мысли, действия) как в Cursor — отправляются до контента
        use_victoria = getattr(message, 'use_victoria', True)
        mode = (getattr(message, 'mode', None) or "agent").lower()
        logger.info(f"[SSE] use_victoria={use_victoria}, mode={mode}")

        # Быстрая проверка Victoria (agent/plan). При недоступности — Agent fallback на MLX/Ollama (как простые)
        victoria_available = True
        if use_victoria and mode in ("agent", "plan"):
            try:
                vh = await asyncio.wait_for(victoria.health(), timeout=5.0)
                if vh.get("status") not in ("healthy", "ok"):
                    victoria_available = False
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning("Victoria health check failed: %s, fallback на MLX/Ollama", e)
                victoria_available = False
            if not victoria_available and mode == "plan":
                # Plan требует Victoria, fallback не применим
                tip = "Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent"
                yield f"data: {json.dumps({'type': 'error', 'content': f'Victoria недоступна. {tip}'})}\n\n"
                yield f"data: {json.dumps({'type': 'end'})}\n\n"
                return

        # Используем только Victoria (приоритет)
        if use_victoria:
            # Используем Victoria с контекстом проекта
            # Victoria сама подключается к Knowledge OS через asyncpg connection pool
            project_context = os.getenv("PROJECT_NAME", "atra-web-ide")

            if mode == "plan":
                # Режим «Только план»: кэш (Фаза 3) или вызов Victoria
                settings = get_settings()
                cache = plan_cache or get_plan_cache_service()
                if getattr(settings, "plan_cache_enabled", True) and cache._maxsize > 0:
                    cached = await cache.get(current_prompt, project_context)
                    if cached:
                        plan_text = cached.get("result") or cached.get("response") or ""
                        if plan_text:
                            logger.info("[Plan] cache hit: '%s...'", (message.content or "")[:40])
                            yield f"data: {json.dumps({'type': 'step', 'stepType': 'action', 'title': 'План из кэша', 'content': 'Использую сохранённый план.'})}\n\n"
                            yield _flush_sse()
                            await asyncio.sleep(0.02)
                            for line in plan_text.split("\n"):
                                if line.strip():
                                    response_parts.append(line + chr(10))
                                    yield f"data: {json.dumps({'type': 'chunk', 'content': line + chr(10)})}\n\n"
                                    await asyncio.sleep(0.01)
                            await _save_context_if_needed()
                            yield f"data: {json.dumps({'type': 'end'})}\n\n"
                            return
                yield f"data: {json.dumps({'type': 'step', 'stepType': 'action', 'title': 'Составляю план', 'content': 'Запрашиваю план у Виктории (без выполнения).'})}\n\n"
                yield _flush_sse()
                await asyncio.sleep(0.05)
                try:
                    import time
                    t0 = time.perf_counter()
                    plan_result = await victoria.plan(goal=current_prompt, project_context=project_context)
                    gen_time = time.perf_counter() - t0
                    plan_text = (plan_result.get("result") or plan_result.get("response") or "") if plan_result.get("status") != "error" else ""
                    if not plan_text:
                        plan_text = plan_result.get("error", "Не удалось получить план.")
                    for line in plan_text.split("\n"):
                        if line.strip():
                            response_parts.append(line + chr(10))
                            yield f"data: {json.dumps({'type': 'chunk', 'content': line + chr(10)})}\n\n"
                            await asyncio.sleep(0.02)
                    await _save_context_if_needed()
                    yield f"data: {json.dumps({'type': 'end'})}\n\n"
                    min_gen = getattr(settings, "plan_cache_min_gen_time", 2.0)
                    if plan_result.get("status") != "error" and plan_text and gen_time >= min_gen and cache._maxsize > 0:
                        await cache.set(current_prompt, plan_result, project_context, ttl=getattr(settings, "plan_cache_ttl", 3600))
                        logger.info("[Plan] saved to cache: '%s...' (gen_time=%.1fs)", (message.content or "")[:40], gen_time)
                    return
                except Exception as e:
                    logger.error(f"Plan mode error: {e}", exc_info=True)
                    yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
                    yield f"data: {json.dumps({'type': 'end'})}\n\n"
                    return

            # Шаг: мысль (анализ запроса). correlation_id для трассировки.
            # Progress event (ARCHITECTURE_IMPROVEMENTS §2.1): { step, total, status } для длинных сценариев
            yield f"data: {json.dumps({'type': 'progress', 'step': 1, 'total': 4, 'status': 'analysis'})}\n\n"
            yield f"data: {json.dumps({'type': 'step', 'stepType': 'thought', 'title': 'Анализ запроса', 'content': 'Проверяю запрос, подбираю эксперта и контекст из базы знаний (RAG).', 'correlation_id': correlation_id})}\n\n"
            yield _flush_sse()
            await asyncio.sleep(0.05)

            # Если указан expert_name, проверяем его в Knowledge OS Database
            expert_data = None
            if message.expert_name:
                try:
                    expert_data = await knowledge_os.get_expert_by_name(message.expert_name)
                    if expert_data:
                        logger.info(f"✅ Эксперт '{message.expert_name}' найден в Knowledge OS: {expert_data.get('role')}")
                        exploration_content = f"Эксперт: {message.expert_name} ({expert_data.get('role', '')})"
                        yield f"data: {json.dumps({'type': 'step', 'stepType': 'exploration', 'title': 'Эксперт найден', 'content': exploration_content})}\n\n"
                        yield _flush_sse()
                        await asyncio.sleep(0.05)
                except Exception as e:
                    logger.debug(f"Эксперт не найден в Knowledge OS: {e}")

            # Шаг: действие (запрос к Victoria)
            yield f"data: {json.dumps({'type': 'progress', 'step': 2, 'total': 4, 'status': 'executing'})}\n\n"
            yield f"data: {json.dumps({'type': 'step', 'stepType': 'action', 'title': 'Запрос к Victoria Agent', 'content': 'Формирую план и запрашиваю ответ у агента.'})}\n\n"
            yield _flush_sse()
            await asyncio.sleep(0.05)

            # Режим Ask: горячий путь (шаблоны) → MLX → Ollama → Victoria
            if mode == "ask":
                # Горячий путь: простые запросы (приветствия, благодарность) — шаблон без LLM
                classification = classify_query(message.content)
                if classification.get("type") == "simple":
                    template = get_template_response(message.content, message.expert_name)
                    if template:
                        query_preview = (message.content or "")[:30].replace("\n", " ")
                        logger.info("[Ask] Hot path: simple query '%s' -> template (no LLM)", query_preview)
                        yield f"data: {json.dumps({'type': 'step', 'stepType': 'action', 'title': 'Быстрый ответ', 'content': 'Шаблонный ответ (без вызова LLM).'})}\n\n"
                        yield _flush_sse()
                        await asyncio.sleep(0.02)
                        for word in template.split():
                            response_parts.append(word + " ")
                            yield f"data: {json.dumps({'type': 'chunk', 'content': word + ' '})}\n\n"
                            await asyncio.sleep(0.01)
                        await _save_context_if_needed()
                        yield f"data: {json.dumps({'type': 'end'})}\n\n"
                        return
                # RAG-light для фактуальных запросов (Фаза 2)
                if classification.get("type") == "factual":
                    settings = get_settings()
                    if getattr(settings, "rag_light_enabled", True):
                        rag_light = get_rag_light_service(knowledge_os)
                        if rag_light.enabled:
                            yield f"data: {json.dumps({'type': 'step', 'stepType': 'action', 'title': 'Быстрый ответ', 'content': 'Ищу ответ в базе знаний (RAG-light)...'})}\n\n"
                            yield _flush_sse()
                            await asyncio.sleep(0.02)
                            try:
                                fast_answer = await rag_light.fast_fact_answer(
                                    message.content,
                                    timeout_ms=getattr(settings, "rag_light_timeout_ms", 200),
                                    user_id=getattr(message, "user_id", None),
                                )
                                if fast_answer:
                                    yield f"data: {json.dumps({'type': 'step', 'stepType': 'action', 'title': 'Найдено в БЗ', 'content': 'Ответ из базы знаний.'})}\n\n"
                                    yield _flush_sse()
                                    await asyncio.sleep(0.02)
                                    for word in fast_answer.split():
                                        response_parts.append(word + " ")
                                        yield f"data: {json.dumps({'type': 'chunk', 'content': word + ' '})}\n\n"
                                        await asyncio.sleep(0.01)
                                    await _save_context_if_needed()
                                    yield f"data: {json.dumps({'type': 'end'})}\n\n"
                                    logger.info("[Ask] RAG-light path: factual query -> answer from KB")
                                    return
                            except Exception as e:
                                logger.debug("RAG-light failed, falling back to MLX/Ollama: %s", e)
                # Подсказка перейти в Агент для сложных запросов (Фаза 2, день 3–4)
                settings = get_settings()
                if getattr(settings, "agent_suggestion_enabled", True):
                    enhanced = analyze_complexity(message.content)
                    if enhanced.get("suggest_agent") and enhanced.get("complexity_score", 0) >= getattr(settings, "agent_suggestion_threshold", 0.6):
                        suggestion_text = (
                            "Этот запрос требует глубокого анализа. "
                            "Для наиболее полного ответа перейдите в режим «Агент». Продолжаю в текущем режиме…"
                        )
                        yield f"data: {json.dumps({'type': 'step', 'stepType': 'thought', 'title': 'Рекомендация', 'content': suggestion_text})}\n\n"
                        yield _flush_sse()
                        delay_ms = getattr(settings, "agent_suggestion_delay_ms", 500)
                        await asyncio.sleep(delay_ms / 1000.0)
                        logger.info(
                            "[Ask] Agent suggestion shown: query='%s...', score=%.2f",
                            (message.content or "")[:30],
                            enhanced.get("complexity_score", 0),
                        )
                        try:
                            agent_suggestion_metrics.add_suggestion(
                                AgentSuggestionMetric(
                                    query=(message.content or "")[:500],
                                    suggested=True,
                                    complexity_score=enhanced.get("complexity_score", 0),
                                    reason=enhanced.get("complexity_reason", ""),
                                    user_action="unknown",
                                )
                            )
                        except Exception:
                            pass
                # Обычный путь: MLX → Ollama → Victoria
                yield f"data: {json.dumps({'type': 'step', 'stepType': 'action', 'title': 'Быстрый ответ', 'content': 'Проверяю MLX и Ollama, при недоступности — Victoria.'})}\n\n"
                yield _flush_sse()
                await asyncio.sleep(0.05)
                expert_prompt = f"Ты - {message.expert_name}, эксперт ATRA. Отвечай кратко.\n\n" if message.expert_name else ""
                full_prompt = expert_prompt + current_prompt
                ideal_model = message.model or _select_model_for_chat(message.content, message.expert_name)
                content, source = await _generate_via_mlx_or_ollama(
                    full_prompt, ideal_model, mlx, ollama,
                    system="Ты - полезный ИИ-ассистент корпорации ATRA. Отвечай кратко на русском.",
                )
                if content:
                    content = _truncate_repeated_response(content)
                    words = content.split()
                    chunk = ""
                    for i, word in enumerate(words):
                        chunk += word + " "
                        if i % 3 == 0 and chunk:
                            response_parts.append(chunk)
                            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                            chunk = ""
                            await asyncio.sleep(0.02)
                    if chunk:
                        response_parts.append(chunk)
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                    await _save_context_if_needed()
                    yield f"data: {json.dumps({'type': 'end'})}\n\n"
                    asyncio.create_task(_log_chat_to_knowledge_os(message.content, content, message.expert_name))
                    return
                # MLX и Ollama не ответили (таймаут, ошибка или модель занята) — отвечаем через Victoria
                yield f"data: {json.dumps({'type': 'step', 'stepType': 'action', 'title': 'Запасной вариант', 'content': 'MLX и Ollama не ответили вовремя — отвечаю через Victoria.'})}\n\n"
                yield _flush_sse()
                await asyncio.sleep(0.05)
                logger.info("[Ask] MLX/Ollama не ответили, fallback на Victoria")

            # 🏛 BOARD OF DIRECTORS CONSULT: классификация стратегического вопроса
            board_decision_text = None
            correlation_id = None
            
            try:
                from app.services.strategic_classifier import is_strategic_question
                
                is_strategic, reason = is_strategic_question(message.content)
                logger.info(f"[STRATEGIC_CLASSIFIER] is_strategic={is_strategic}, reason={reason}, question='{message.content[:100]}...'")
                
                if is_strategic:
                    # Генерируем correlation_id для трассировки
                    import uuid
                    correlation_id = str(uuid.uuid4())
                    
                    # Показываем пользователю, что консультируемся с Советом
                    yield f"data: {json.dumps({'type': 'step', 'stepType': 'thought', 'title': 'Консультация Совета Директоров', 'content': 'Этот вопрос стратегический. Консультируюсь с Советом Директоров для принятия решения...'})}\n\n"
                    yield _flush_sse()
                    await asyncio.sleep(0.1)
                    
                    # Вызов Knowledge OS API: POST /api/board/consult
                    settings_board = get_settings()
                    board_api_url = f"{settings_board.knowledge_os_api_url.rstrip('/')}/api/board/consult"
                    api_key = os.getenv('API_KEY', 'your-secret-api-key')
                    
                    try:
                        async with httpx.AsyncClient(timeout=45.0) as client:
                            board_response = await client.post(
                                board_api_url,
                                json={
                                    "question": message.content,
                                    "session_id": session_id,
                                    "user_id": getattr(message, 'user_id', None),
                                    "correlation_id": correlation_id,
                                    "source": "chat",
                                },
                                headers={"X-API-Key": api_key}
                            )
                            board_response.raise_for_status()
                            board_result = board_response.json()
                            
                            board_decision_text = board_result.get("directive_text", "")
                            structured_decision = board_result.get("structured_decision", {})
                            risk_level = board_result.get("risk_level")
                            recommend_review = board_result.get("recommend_human_review", False)
                            
                            logger.info(f"[BOARD_CONSULT] success correlation_id={correlation_id} decision='{structured_decision.get('decision', '')[:80]}...' risk={risk_level}")
                            
                            # Показываем решение Совета пользователю
                            decision_summary = structured_decision.get("decision", board_decision_text[:150])
                            board_step_content = f"Совет Директоров принял решение:\n\n{decision_summary}"
                            if recommend_review:
                                board_step_content += "\n\n⚠️ Совет рекомендует подтверждение этого решения человеком (высокий риск или низкая уверенность)."
                            
                            yield f"data: {json.dumps({'type': 'step', 'stepType': 'observation', 'title': 'Решение Совета', 'content': board_step_content})}\n\n"
                            yield _flush_sse()
                            await asyncio.sleep(0.1)
                            
                    except httpx.HTTPError as e:
                        logger.error(f"[BOARD_CONSULT] HTTP error: {e}")
                        yield f"data: {json.dumps({'type': 'step', 'stepType': 'error', 'title': 'Ошибка консультации Совета', 'content': f'Не удалось получить решение Совета: {str(e)}. Продолжаю с Victoria...'})}\n\n"
                        yield _flush_sse()
                        board_decision_text = None
                    except Exception as e:
                        logger.error(f"[BOARD_CONSULT] error: {e}", exc_info=True)
                        yield f"data: {json.dumps({'type': 'step', 'stepType': 'error', 'title': 'Ошибка консультации Совета', 'content': f'Ошибка при консультации Совета: {str(e)}. Продолжаю с Victoria...'})}\n\n"
                        yield _flush_sse()
                        board_decision_text = None
            except ImportError:
                logger.warning("[STRATEGIC_CLASSIFIER] strategic_classifier module not found, skipping board consult")
            except Exception as e:
                logger.error(f"[STRATEGIC_CLASSIFIER] unexpected error: {e}", exc_info=True)
            
            # Если получено решение Совета, формируем расширенный промпт для Victoria
            if board_decision_text:
                board_prompt_block = f"""
[РЕШЕНИЕ СОВЕТА ДИРЕКТОРОВ]
{board_decision_text}
[/РЕШЕНИЕ]

Запрос пользователя: {message.content}

Инструкция: Сформулируй ответ пользователю, опираясь на решение Совета Директоров выше. 
Можешь начать с фразы "По решению Совета Директоров..." и далее развить ответ с учётом решения.
Если решение содержит рекомендацию подтверждения человеком, обязательно упомяни это в конце.
"""
                current_prompt = board_prompt_block
            
            # Вызываем Victoria с таймаутом (тяжёлые модели: прогрев + обработка локальными моделями)
            # session_id и chat_history для Victoria (контракт POST /run, связный диалог)
            chat_history_vic = []
            if session_id and recent_messages:
                ctx_mgr = get_conversation_context_manager()
                chat_history_vic = ctx_mgr.to_victoria_chat_history(recent_messages)
            settings = get_settings()
            try:
                result = await asyncio.wait_for(
                    victoria.run(
                        prompt=current_prompt,
                        expert_name=message.expert_name,
                        project_context=project_context,
                        session_id=session_id,
                        chat_history=chat_history_vic if chat_history_vic else None,
                        correlation_id=correlation_id,
                    ),
                    timeout=settings.victoria_timeout  # по умолчанию 600 сек
                )
            except asyncio.TimeoutError:
                logger.error(f"Victoria timeout для запроса (limit {settings.victoria_timeout}s): {message.content[:50]}")
                yield f"data: {json.dumps({'type': 'progress', 'step': 4, 'total': 4, 'status': 'error'})}\n\n"
                error_event = {
                    'type': 'error',
                    'content': 'Превышено время ожидания ответа от Victoria. Попробуйте переформулировать вопрос или использовать более простой запрос.'
                }
                yield f"data: {json.dumps(error_event)}\n\n"
                yield f"data: {json.dumps({'type': 'end'})}\n\n"
                return
            except Exception as e:
                logger.error(f"Victoria error: {e}", exc_info=True)
                result = {"error": str(e)}
            
            # Уточняющие вопросы от Victoria — показываем в чате как шаг и текст
            if result.get("status") == "needs_clarification":
                questions = result.get("clarification_questions") or result.get("raw", {}).get("clarification_questions") or []
                text = "Нужно уточнение:\n\n" + "\n".join(f"• {q}" for q in questions) if questions else "Виктория просит уточнить задачу."
                yield f"data: {json.dumps({'type': 'step', 'stepType': 'clarification', 'title': 'Уточняющие вопросы', 'content': text})}\n\n"
                yield _flush_sse()
                await asyncio.sleep(0.05)
                for line in text.split("\n"):
                    if line.strip():
                        response_parts.append(line + chr(10))
                        yield f"data: {json.dumps({'type': 'chunk', 'content': line + chr(10)})}\n\n"
                        await asyncio.sleep(0.02)
                await _save_context_if_needed()
                yield f"data: {json.dumps({'type': 'progress', 'step': 4, 'total': 4, 'status': 'complete'})}\n\n"
                yield f"data: {json.dumps({'type': 'end'})}\n\n"
                return

            if "error" in result:
                # Fallback: MLX → Ollama (Victoria уже недоступна)
                yield f"data: {json.dumps({'type': 'step', 'stepType': 'action', 'title': 'Запасной вариант', 'content': 'Victoria недоступна — проверяю MLX и Ollama.'})}\n\n"
                yield _flush_sse()
                await asyncio.sleep(0.05)
                logger.warning("Victoria недоступна, используем MLX → Ollama как fallback")

                expert_prompt = ""
                if message.expert_name:
                    expert_prompt = f"Ты - {message.expert_name}, эксперт ATRA. Отвечай кратко и по делу.\n\n"
                full_prompt = expert_prompt + current_prompt
                ideal_model = message.model or _select_model_for_chat(message.content, message.expert_name)
                content, source = await _generate_via_mlx_or_ollama(
                    full_prompt, ideal_model, mlx, ollama,
                    system="Ты - полезный ИИ-ассистент корпорации ATRA. Отвечай кратко на русском.",
                )

                if not content:
                    fallback_response = (
                        f"Привет! Я {message.expert_name or 'Виктория'}. "
                        "Сейчас недоступны Victoria, MLX и Ollama. Запустите один из серверов или попробуйте позже."
                    )
                    words = fallback_response.split()
                    buffer = ""
                    for i, word in enumerate(words):
                        buffer += word + " "
                        if i % 5 == 0:
                            response_parts.append(buffer)
                            yield f"data: {json.dumps({'type': 'chunk', 'content': buffer})}\n\n"
                            buffer = ""
                    if buffer:
                        response_parts.append(buffer)
                        yield f"data: {json.dumps({'type': 'chunk', 'content': buffer})}\n\n"
                    await _save_context_if_needed()
                    yield f"data: {json.dumps({'type': 'end'})}\n\n"
                    return
                result = {"response": content, "source": source}
            else:
                # Victoria успешно ответила
                yield f"data: {json.dumps({'type': 'progress', 'step': 4, 'total': 4, 'status': 'complete'})}\n\n"
                yield f"data: {json.dumps({'type': 'step', 'stepType': 'action', 'title': 'Генерация ответа', 'content': 'Формирую ответ.'})}\n\n"
                yield _flush_sse()
                await asyncio.sleep(0.05)
                content = result.get("result", "") or result.get("response", "") or result.get("output", "")
                if not content:
                    logger.warning(f"Victoria вернула пустой ответ: {result}")
                    content = f"Привет! Я {message.expert_name or 'Виктория'}. Получила ваш запрос, но ответ пока пустой. Попробуйте переформулировать вопрос."
                else:
                    # Убираем начальное сообщение "Обрабатываю..." если оно есть в ответе
                    if "Обрабатываю" in content:
                        # Оставляем только реальный ответ после "Обрабатываю..."
                        parts = content.split("Обрабатываю")
                        if len(parts) > 1:
                            content = parts[-1].strip()
                            if not content:
                                content = "Обрабатываю ваш запрос..."
                    content = _truncate_repeated_response(content)
                
                # Разбиваем на слова для плавного отображения
                words = content.split()
                buffer = ""
                for i, word in enumerate(words):
                    buffer += word + " "
                    if i % 5 == 0:  # Отправляем каждые 5 слов
                        response_parts.append(buffer)
                        yield f"data: {json.dumps({'type': 'chunk', 'content': buffer})}\n\n"
                        buffer = ""
                        await asyncio.sleep(0.05)  # Небольшая задержка для плавности
                
                if buffer:
                    response_parts.append(buffer)
                    yield f"data: {json.dumps({'type': 'chunk', 'content': buffer})}\n\n"
                
                # Логируем в interaction_logs (Singularity 9.0)
                asyncio.create_task(_log_chat_to_knowledge_os(message.content, content, message.expert_name))
                await _save_context_if_needed()
                # Отправляем событие завершения (progress уже отправлен выше)
                yield f"data: {json.dumps({'type': 'end'})}\n\n"
                return
            
            # Обработка результата от MLX fallback (если Victoria была недоступна)
            if result and isinstance(result, dict) and result.get("response"):
                content = result.get("response", "")
                content = _truncate_repeated_response(content)
                source = result.get("source", "unknown")
                model_used = result.get("model", "unknown")
                logger.info(f"✅ Ответ получен от {source} (модель: {model_used}) через fallback")
                
                # Отправляем по словам для плавного отображения
                words = content.split()
                chunk = ""
                for i, word in enumerate(words):
                    chunk += word + " "
                    if i % 3 == 0 and chunk:  # Каждые 3 слова
                        response_parts.append(chunk)
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                        chunk = ""
                        await asyncio.sleep(0.05)  # Задержка для плавности
                if chunk:
                    response_parts.append(chunk)
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                
                # Логируем в interaction_logs (Singularity 9.0)
                asyncio.create_task(_log_chat_to_knowledge_os(message.content, content, message.expert_name))
                await _save_context_if_needed()
                # Отправляем событие завершения
                yield f"data: {json.dumps({'type': 'end'})}\n\n"
                return
        else:
            # Если use_victoria=False: MLX → Ollama (без Victoria)
            expert_prompt = ""
            if message.expert_name:
                expert_prompt = f"Ты - {message.expert_name}, эксперт ATRA. Отвечай кратко и по делу.\n\n"
            full_prompt = expert_prompt + current_prompt
            ideal_model = message.model or _select_model_for_chat(message.content, message.expert_name)
            logger.info(f"🎯 Идеальная модель для '{message.content[:50]}...': {ideal_model}")

            content, source = await _generate_via_mlx_or_ollama(
                full_prompt, ideal_model, mlx, ollama,
                system="Ты - полезный ИИ-ассистент корпорации ATRA. Отвечай кратко на русском.",
            )

            if not content:
                logger.warning("MLX и Ollama недоступны (use_victoria=False)")
                expert_name = message.expert_name or "ассистент"
                fallback_response = (
                    f"Привет! Я {expert_name}. Сейчас недоступны MLX и Ollama. "
                    "Запустите один из серверов или используйте режим Агент (Victoria)."
                )
                words = fallback_response.split()
                chunk = ""
                for i, word in enumerate(words):
                    chunk += word + " "
                    if i % 3 == 0 and chunk:
                        response_parts.append(chunk)
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                        chunk = ""
                if chunk:
                    response_parts.append(chunk)
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                await _save_context_if_needed()
                yield f"data: {json.dumps({'type': 'end'})}\n\n"
                return
            # Ответ от MLX или Ollama
            logger.info(f"✅ Ответ получен от {source}")
            content = _truncate_repeated_response(content)
            words = content.split()
            chunk = ""
            for i, word in enumerate(words):
                chunk += word + " "
                if i % 3 == 0 and chunk:
                    response_parts.append(chunk)
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                    chunk = ""
                    await asyncio.sleep(0.05)
            if chunk:
                response_parts.append(chunk)
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            asyncio.create_task(_log_chat_to_knowledge_os(message.content, content, message.expert_name))
            await _save_context_if_needed()
            yield f"data: {json.dumps({'type': 'end'})}\n\n"
            return

        # Отправляем завершение (для путей без return выше)
        yield f"data: {json.dumps({'type': 'end'})}\n\n"
        
    except Exception as e:
        logger.error(f"SSE error: {e}", exc_info=True)
        # Вместо отправки error, отправляем fallback ответ
        expert_name = message.expert_name or "ассистент"
        fallback_response = f"Привет! Я {expert_name}. Произошла ошибка при обработке запроса: {str(e)[:100]}. Попробуйте позже."
        words = fallback_response.split()
        chunk = ""
        for i, word in enumerate(words):
            chunk += word + " "
            if i % 3 == 0 and chunk:
                response_parts.append(chunk)
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                chunk = ""
        if chunk:
            response_parts.append(chunk)
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
        try:
            await _save_context_if_needed()
        except Exception:
            pass
        yield f"data: {json.dumps({'type': 'end'})}\n\n"


@router.post("/send", response_model=ChatResponse)
async def send_message(
    message: ChatMessage,
    victoria: VictoriaClient = Depends(get_victoria_client)
) -> ChatResponse:
    """
    Отправить сообщение (не-стриминг)
    
    Returns:
        Ответ от чата
    """
    try:
        correlation_id = str(uuid.uuid4())
        session_id = getattr(message, "session_id", None) or getattr(message, "user_id", None)
        chat_history_vic = []
        if session_id:
            ctx_mgr = get_conversation_context_manager()
            recent = await ctx_mgr.get_recent(session_id, last_n=10)
            chat_history_vic = ctx_mgr.to_victoria_chat_history(recent)

        prompt_for_victoria = message.content
        try:
            from app.services.strategic_classifier import is_strategic_question
            is_strategic, _ = is_strategic_question(message.content)
            if is_strategic:
                settings_send = get_settings()
                board_api_url = f"{settings_send.knowledge_os_api_url.rstrip('/')}/api/board/consult"
                api_key = os.environ.get("API_KEY", "your-secret-api-key")
                async with httpx.AsyncClient(timeout=45.0) as client:
                    board_response = await client.post(
                        board_api_url,
                        json={
                            "question": message.content,
                            "session_id": session_id,
                            "user_id": getattr(message, "user_id", None),
                            "correlation_id": correlation_id,
                            "source": "chat",
                        },
                        headers={"X-API-Key": api_key},
                    )
                    board_response.raise_for_status()
                    board_result = board_response.json()
                    directive_text = board_result.get("directive_text", "")
                    if directive_text:
                        prompt_for_victoria = f"""[РЕШЕНИЕ СОВЕТА ДИРЕКТОРОВ]
{directive_text}
[/РЕШЕНИЕ]

Запрос пользователя: {message.content}

Инструкция: Сформулируй ответ пользователю, опираясь на решение Совета Директоров выше. Можешь начать с фразы "По решению Совета Директоров..."."""
        except Exception as e:
            logger.debug("Board consult skipped for send_message: %s", e)

        result = await victoria.run(
            prompt=prompt_for_victoria,
            expert_name=message.expert_name,
            session_id=session_id,
            chat_history=chat_history_vic if chat_history_vic else None,
            correlation_id=correlation_id,
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=500,
                detail=result["error"]
            )
        
        content = result.get("result", "") or result.get("response", "")
        asyncio.create_task(_log_chat_to_knowledge_os(message.content, content, message.expert_name))
        return ChatResponse(
            content=content,
            expert_name=message.expert_name,
            model=result.get("model")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat send error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing chat message"
        )


@router.post("/plan", response_model=PlanResponse)
@prometheus_metrics.track_request(mode="plan", endpoint="plan")
async def get_plan(
    body: PlanRequest,
    victoria: VictoriaClient = Depends(get_victoria_client),
    plan_cache: PlanCacheService = Depends(get_plan_cache_service),
) -> PlanResponse:
    """
    Получить только план по задаче (без выполнения). Как вкладка «План» в Cursor.
    Фаза 3: при включённом кэше повторные запросы по тому же goal возвращаются из кэша.
    """
    try:
        settings = get_settings()
        project_context = settings.project_name
        PLAN_REQUESTS.inc()
        t0 = time.perf_counter()
        if getattr(settings, "plan_cache_enabled", True) and plan_cache._maxsize > 0:
            cached = await plan_cache.get(body.goal, project_context)
            if cached:
                plan = cached.get("result", "") or cached.get("response", "") or ""
                if plan:
                    logger.info("[Plan] cache hit (POST /plan): '%s...'", (body.goal or "")[:40])
                    PLAN_DURATION.observe(time.perf_counter() - t0)
                    return PlanResponse(plan=plan, status="success")
        acquired = await acquire_victoria_slot()
        if not acquired:
            raise HTTPException(
                status_code=503,
                detail="Service busy (Victoria limit). Retry later.",
                headers={"Retry-After": "60"},
            )
        try:
            result = await victoria.plan(goal=body.goal, project_context=project_context)
        finally:
            release_victoria_slot()
        gen_time = time.perf_counter() - t0
        PLAN_DURATION.observe(gen_time)
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error", "Plan failed"))
        plan = result.get("result", "") or result.get("response", "") or ""
        steps = result.get("steps") or []
        if isinstance(steps, list) and steps:
            PLAN_STEPS_COUNT.observe(len(steps))
        min_gen = getattr(settings, "plan_cache_min_gen_time", 2.0)
        if plan and gen_time >= min_gen and plan_cache._maxsize > 0:
            await plan_cache.set(body.goal, result, project_context, ttl=getattr(settings, "plan_cache_ttl", 3600))
            logger.info("[Plan] saved to cache (POST /plan): '%s...' (gen_time=%.1fs)", (body.goal or "")[:40], gen_time)
        return PlanResponse(plan=plan, status="success")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Plan error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while getting plan")


@router.post("/stream", response_model=None)
@prometheus_metrics.track_request(mode="stream", endpoint="stream")
async def stream_message(
    message: ChatMessage,
    victoria: VictoriaClient = Depends(get_victoria_client),
    mlx: MLXClient = Depends(get_mlx_client),
    ollama: OllamaClient = Depends(get_ollama_client),
    knowledge_os: KnowledgeOSClient = Depends(get_knowledge_os_client),
):
    """
    SSE стриминг ответа (Singularity 9.0).
    Цепочка выбора: MLX → Ollama → Victoria.
    При перегрузке (лимит слотов Victoria) — 503.
    Возвращает StreamingResponse или JSONResponse(503).
    """
    acquired = await acquire_victoria_slot()
    if not acquired:
        return JSONResponse(
            status_code=503,
            content={
                "error": "service_busy",
                "detail": "Too many concurrent requests. Retry later.",
            },
            headers={"Retry-After": "60"},
        )
    plan_cache = get_plan_cache_service()
    return StreamingResponse(
        with_victoria_slot(
            sse_generator(message, victoria, mlx, ollama, knowledge_os, plan_cache)
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/status")
async def chat_status(
    victoria: VictoriaClient = Depends(get_victoria_client),
    mlx: MLXClient = Depends(get_mlx_client),
    ollama: OllamaClient = Depends(get_ollama_client),
) -> dict:
    """
    Статус сервисов чата (цепочка: MLX → Ollama → Victoria).
    """
    try:
        victoria_health = await victoria.health()
        mlx_health = await mlx.health()
        ollama_health = await ollama.health()
        return {
            "victoria": victoria_health,
            "mlx": mlx_health,
            "ollama": ollama_health,
        }
    except Exception as e:
        logger.error(f"Chat status error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error checking chat services status"
        )


@router.get("/classify")
async def classify_query_endpoint(q: str = "") -> dict:
    """
    Проверка классификатора запросов (для тестов и отладки).
    GET /api/chat/classify?q=привет
    Возвращает classification + suggest_agent, complexity_score, complexity_reason (Фаза 2).
    """
    from app.services.query_classifier import classify_query, get_template_response, analyze_complexity
    classification = analyze_complexity(q)
    template = get_template_response(q, None) if classification.get("type") == "simple" else None
    return {
        "query": q[:200],
        "classification": classification,
        "template_response": template,
    }


@router.get("/agent-suggestions/stats")
async def agent_suggestions_stats() -> dict:
    """
    Метрики рекомендаций перехода в режим Агент (Фаза 2, день 3–4).
    GET /api/chat/agent-suggestions/stats
    """
    return agent_suggestion_metrics.get_stats()


@router.get("/mode/health")
async def mode_health(
    victoria: VictoriaClient = Depends(get_victoria_client),
    mlx: MLXClient = Depends(get_mlx_client),
    ollama: OllamaClient = Depends(get_ollama_client),
) -> dict:
    """
    Доступность бэкендов по режимам (Ask / Agent / Plan).
    Для градации путей и мониторинга.
    """
    try:
        victoria_health = await victoria.health()
        mlx_health = await mlx.health()
        ollama_health = await ollama.health()
        v_ok = victoria_health.get("status") == "ok"
        m_ok = mlx_health.get("status") in ("healthy", "degraded")
        o_ok = ollama_health.get("status") == "healthy"
        return {
            "ask": {
                "mlx": mlx_health.get("status", "unknown"),
                "ollama": ollama_health.get("status", "unknown"),
                "victoria_fallback": victoria_health.get("status", "unknown"),
                "hot_path_available": True,
                "_available": m_ok or o_ok or v_ok,  # хотя бы один бэкенд для Ask
            },
            "agent": {
                "victoria": victoria_health.get("status", "unknown"),
                "fallback_mlx_ollama": m_ok or o_ok,
                "_available": v_ok or (m_ok or o_ok),  # Victoria или fallback
            },
            "plan": {
                "victoria_plan": victoria_health.get("status", "unknown"),
                "_available": v_ok,
            },
        }
    except Exception as e:
        logger.error(f"Mode health error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error checking mode health"
        )


@router.get("/mlx/metrics")
async def get_mlx_metrics(
    mlx: MLXClient = Depends(get_mlx_client)
) -> dict:
    """
    Детальные метрики MLX API Server
    
    Returns:
        Полная информация о загрузке, памяти, моделях и запросах
    """
    try:
        mlx_health = await mlx.health()
        return mlx_health
    except Exception as e:
        logger.error(f"MLX metrics error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error getting MLX metrics: {str(e)}"
        )


@router.get("/models")
async def list_models(
    mlx: MLXClient = Depends(get_mlx_client)
) -> dict:
    """
    Список доступных моделей
    
    Returns:
        Список моделей MLX
    """
    cache = get_cache()
    cache_key = "mlx:models"
    
    # Проверяем кэш
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    
    try:
        mlx_health = await mlx.health()
        # MLX API Server возвращает список моделей в health
        # Получаем список моделей из MLX API Server
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            mlx_response = await client.get("http://localhost:11435/api/tags")
            if mlx_response.status_code == 200:
                mlx_data = mlx_response.json()
                models_list = mlx_data.get("models", [])
            else:
                models_list = []
        
        result = {
            "models": [
                {
                    "name": m.get("name", "unknown"),
                    "size": m.get("size"),
                    "modified": m.get("modified_at")
                }
                for m in models
            ]
        }
        
        # Сохраняем в кэш (1 минута)
        cache.set(cache_key, result, ttl=60)
        
        return result
    except Exception as e:
        logger.error(f"List models error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error fetching models list"
        )
