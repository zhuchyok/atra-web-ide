"""
Прокси Anthropic Messages API → Victoria POST /run.

Позволяет Claude Code (и другим клиентам Anthropic API) использовать Victoria,
экспертов и оркестраторов: запрос приходит в формате Anthropic, прокси переводит
его в POST /run к Victoria и возвращает ответ в формате Anthropic.

Запуск: VICTORIA_URL=http://localhost:8010 uvicorn proxy.main:app --host 0.0.0.0 --port 8040
На 185: VICTORIA_URL=http://localhost:8010 uvicorn proxy.main:app --host 0.0.0.0 --port 8040
"""

import asyncio
import json
import os
import time
import uuid
import logging
from typing import Optional, AsyncGenerator, List

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
import asyncio

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010").rstrip("/")
# Авто-определение: если мы в Docker и victoria-agent доступен, переключаемся
if os.path.exists("/.dockerenv") and VICTORIA_URL == "http://localhost:8010":
    VICTORIA_URL = "http://victoria-agent:8000"

VICTORIA_TIMEOUT = float(os.getenv("VICTORIA_PROXY_TIMEOUT", "30"))  # 30 sec for requests
# Префикс в ответе, чтобы в Claude Code было видно, что отвечает Виктория (модель под капотом может называться Qwen и т.д.)
VICTORIA_RESPONSE_PREFIX = os.getenv("VICTORIA_RESPONSE_PREFIX", "Виктория (корпорация): ").strip()

# Multiple parallel requests OK
_victoria_semaphore = asyncio.Semaphore(10)

# Хранилище диалогов: session_id → [{"user": "...", "assistant": "..."}]
_dialogue_store: dict[str, list[dict]] = {}

# [SINGULARITY 10.0] Support for 'discuss' model - Team Discussion Engine
import sys
ko_path = "/Users/bikos/Documents/atra-web-ide/knowledge_os/app"
if ko_path not in sys.path:
    sys.path.insert(0, ko_path)
try:
    from ai_core import TeamDiscussionEngine
except ImportError:
    TeamDiscussionEngine = None

app = FastAPI(
    title="Claude Code → Victoria Proxy",
    description="Anthropic Messages API compatible proxy to Victoria (experts, orchestrators)",
    version="1.0.0",
)


# --- Anthropic request: messages[] with role/content ---


def _extract_last_user_text(messages: list[dict]) -> str:
    """Из списка messages (сырой JSON) берём последнее сообщение пользователя (role=user) и извлекаем текст.
    Также учитываем результаты инструментов (tool_result), если они есть."""
    parts = []
    for m in reversed(messages):
        role = m.get("role")
        content = m.get("content")
        
        if role == "user":
            text = _extract_text_from_content(content)
            if text:
                parts.append(text.strip())
        if parts:
            break
    
    return "\n\n".join(reversed(parts)).strip()


def _extract_text_from_content(content) -> str:
    """Универсальное извлечение текста из content (строка или массив block'ов)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and "text" in block:
                    parts.append(block["text"])
                elif block.get("type") == "tool_result":
                    parts.append(f"[Результат: {block.get('content', '')}]")
        return "".join(parts)
    return ""


# --- Victoria: POST /run → TaskResponse ---
async def call_victoria_run(goal: str, correlation_id: str, chat_history: Optional[List[dict]] = None, category: Optional[str] = None) -> dict:
    """Вызов Victoria POST /run (синхронный режим)."""
    logger.info("[call_victoria] connecting to %s/run with goal=%s, category=%s", VICTORIA_URL, goal[:50], category)
    payload = {"goal": goal}
    if category:
        payload["category"] = category
    if chat_history:
        payload["chat_history"] = chat_history
    # X-Forwarded-For явно ставим в 127.0.0.1 — иначе Victoria видит GitHub CDN IP (185.199.x.x)
    # от Claude Code/OpenCode и считает его внешним клиентом (rate-limit/блокировка).
    headers = {"Content-Type": "application/json", "X-Correlation-ID": correlation_id, "X-Forwarded-For": "127.0.0.1"}
    # Увеличиваем таймаут для всех запросов, так как локальные модели могут быть медленными
    timeout = httpx.Timeout(VICTORIA_TIMEOUT, connect=10.0, read=VICTORIA_TIMEOUT - 10.0)
    last_error = None
    async with _victoria_semaphore:
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(
                        f"{VICTORIA_URL}/run",
                        json=payload,
                        headers=headers,
                        params={"async_mode": "false"},
                    )
                logger.info("[call_victoria] got response from Victoria, status=%s", resp.status_code)
                return resp.json()
            except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ConnectError) as e:
                last_error = e
                logger.warning(
                    "Victoria connection error (attempt %s/3, correlation_id=%s): %s [%s]",
                    attempt + 1, correlation_id, (e.args[0] if e.args else ""), type(e).__name__,
                )
                if attempt < 2:
                    await asyncio.sleep(2.0 * (attempt + 1))
                continue
    logger.error("Victoria unreachable after 3 attempts: %s [%s]", last_error, type(last_error).__name__ if last_error else "?")
    raise HTTPException(
        status_code=503,
        detail="Victoria disconnected or timed out. Try again or check Victoria (8010) is running.",
    )


# --- Anthropic streaming SSE (для Claude Code: stream=true) ---
async def stream_anthropic_sse(
    text: str,
    request_id: str,
    model: Optional[str] = None,
    chunk_size: int = 3,
) -> AsyncGenerator[str, None]:
    """
    Генерирует SSE в формате Anthropic Messages Streaming.
    Текст от Victoria разбивается по словам и отдаётся как content_block_delta.
    """
    model_id = model or "victoria-via-proxy"
    # message_start
    msg_start = json.dumps({
        "type": "message_start",
        "message": {
            "id": request_id,
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": model_id,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_creation_input_tokens": None,
                "cache_read_input_tokens": None,
            },
        },
    })
    yield f"event: message_start\ndata: {msg_start}\n\n"
    # content_block_start (text, empty)
    block_start = json.dumps({
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    })
    yield f"event: content_block_start\ndata: {block_start}\n\n"
    # content_block_delta — по кускам (слова)
    words = (text or "").split()
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i : i + chunk_size]) + (" " if i + chunk_size < len(words) else "")
        if chunk:
            delta_data = json.dumps({
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": chunk},
            })
            yield f"event: content_block_delta\ndata: {delta_data}\n\n"
    # content_block_stop
    block_stop = json.dumps({"type": "content_block_stop", "index": 0})
    yield f"event: content_block_stop\ndata: {block_stop}\n\n"
    # message_delta
    out_tokens = max(0, len(words))
    msg_delta = json.dumps({
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": out_tokens},
    })
    yield f"event: message_delta\ndata: {msg_delta}\n\n"
    # message_stop
    msg_stop = json.dumps({"type": "message_stop"})
    yield f"event: message_stop\ndata: {msg_stop}\n\n"


# --- Anthropic response (minimal compatible) ---
def build_anthropic_response(text: str, request_id: str, model: Optional[str] = None) -> dict:
    """Собираем ответ в формате Anthropic Messages API."""
    return {
        "id": request_id,
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text or ""}],
        "model": model or "victoria-via-proxy",
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 0,
            "output_tokens": max(0, len((text or "").split())),
            "cache_creation_input_tokens": None,
            "cache_read_input_tokens": None,
        },
    }


@app.get("/v1/models")
async def list_models():
    """Список доступных моделей (OpenAI совместимый)."""
    return JSONResponse(content={
        "object": "list",
        "data": [
            {
                "id": "victoria-wisdom-v3.5",
                "object": "model",
                "created": 1700000000,
                "owned_by": "atra-corporation",
                "permission": [],
                "root": "victoria-wisdom-v3.5",
            },
            {
                "id": "discuss",
                "object": "model",
                "created": 1700000000,
                "owned_by": "atra-corporation",
                "permission": [],
                "root": "discuss",
            }
        ]
    })


@app.get("/health")
async def health():
    """Health check."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            vic_resp = await client.get(f"{VICTORIA_URL}/health")
            victoria_ok = vic_resp.status_code == 200
    except Exception:
        victoria_ok = False

    return JSONResponse(content={
        "status": "ok",
        "proxy": "anthropic-victoria",
        "victoria_url": VICTORIA_URL,
        "victoria_reachable": victoria_ok,
    })


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI Chat Completions → Victoria /run.
    Конвертирует OpenAI формат в Anthropic и вызывает Victoria.
    Поддерживает диалоги: история хранится в памяти и передаётся в Victoria.
    """
    body = await request.json()
    messages_as_dicts = body.get("messages", [])
    model = body.get("model", "victoria-wisdom-v3.5")
    request_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    
    # Получаем или создаём session_id (OpenAI использует metadata для сессий)
    session_id = body.get("metadata", {}).get("session_id") or \
                 request.headers.get("X-Session-ID") or \
                 f"session-{uuid.uuid4().hex[:8]}"
    
    # Строим историю диалога из предыдущих сообщений
    chat_history = []
    for m in messages_as_dicts[:-1]:  # все кроме последнего
        role = m.get("role", "")
        content = _extract_text_from_content(m.get("content"))
        if role == "user":
            chat_history.append({"user": content, "assistant": ""})
        elif role == "assistant" and chat_history and not chat_history[-1]["assistant"]:
            chat_history[-1]["assistant"] = content
        elif role == "assistant":
            chat_history.append({"user": "", "assistant": content})
    
    # Последнее сообщение пользователя
    goal = _extract_last_user_text(messages_as_dicts)
    if not goal:
        raise HTTPException(status_code=400, detail="No user message text found in messages")

    logger.info("[PROXY] goal_preview=%s session=%s model=%s", goal[:80], session_id, model)
    logger.info("[PROXY] calling Victoria...")

    # [SINGULARITY 10.0] Support for 'discuss' model - Team Discussion Engine
    if model in ("discuss", "victoria-discuss"):
        # Увеличиваем таймаут для discuss модели до 1200 секунд
        global VICTORIA_TIMEOUT
        VICTORIA_TIMEOUT = 1200.0
        
        try:
            if TeamDiscussionEngine is None:
                raise ImportError("TeamDiscussionEngine not found")
            
            engine = TeamDiscussionEngine()
            # Для простоты выбираем 3 ключевых экспертов: Виктория, Игорь, Анна
            # В будущем можно выбирать динамически через query_orchestrator
            experts = ["Виктория", "Игорь", "Анна"]
            
            # Генерируем диалог
            discussion_prompt = f"[SYSTEM: TEAM_DISCUSSION_MODE]\nВы - команда экспертов ATRA: {', '.join(experts)}.\nВаша задача: провести живое обсуждение запроса пользователя, используя ваши уникальные стили и характеры из TEAM_PERSONALITIES.MD.\n"
            discussion_prompt += """
            ПРАВИЛА ОБСУЖДЕНИЯ:
            1. Каждый эксперт должен высказать свое мнение.
            2. Игорь (Backend Developer) - технический перфекционист, любит детали, немного саркастичен.
            3. Анна (QA Engineer) - внимательная проверяющая, ищет подвохи, задает вопросы "А что если...".
            4. Виктория (Team Lead) - спокойный координатор, подводит итог.
            5. Используйте Markdown.
            6. НЕ ИСПОЛЬЗУЙТЕ теги <think>. Сразу выводите диалог.
            7. НЕ ВЫВОДИТЕ описание ролей или TEAM_PERSONALITIES.MD. Только сам диалог.
            
            ФОРМАТ ОТВЕТА (ТОЛЬКО ЭТО, БЕЗ ПРЕФИКСОВ):
            **Виктория**: [реплика]
            **Игорь**: [реплика]
            **Анна**: [реплика]
            **Виктория**: [итог]
            
            ЗАПРОС ПОЛЬЗОВАТЕЛЯ: """ + goal
            
            logger.info("[PROXY] calling Victoria with goal length %d", len(discussion_prompt))
            # Simple call without category override
            vic_response = await call_victoria_run(discussion_prompt, request_id, chat_history=chat_history)
            logger.info("[PROXY] got Victoria response, status=%s", vic_response.get("status"))
            
            # [SINGULARITY 10.13] Фикс: если Victoria вернула ошибку таймаута, 
            # мы можем предложить пользователю подождать или использовать другую модель.
            status = vic_response.get("status", "")
            output = vic_response.get("output") or vic_response.get("error") or f"Status: {status}"
            
            if status == "failed" and "timeout" in str(vic_response.get("knowledge", {}).get("error", "")):
                output = "⚠️ **Локальная модель (Wisdom 35B) перегружена.**\n\nГенерация диалога заняла более 5 минут. Это обычно происходит, когда Mac Studio выполняет другие тяжелые задачи (например, воркеры обучают модели или индексируют файлы).\n\n**Что можно сделать:**\n1. Попробуйте отправить запрос еще раз через минуту.\n2. Убедитесь, что в системе нет зависших тяжелых процессов."
            
            text = str(output)
            
            # Проверяем stream parameter
            stream = body.get("stream", False)

            # Очистка от <think> и системных префиксов ПЕРЕД стримингом или возвратом
            if text:
                import re
                # 1. Удаляем все от <think> до </think> или до конца
                text = re.sub(r'<think>.*?(</think>|$)', '', text, flags=re.DOTALL).strip()
                # 2. Удаляем любые теги вида <d...>...</d...> или <dexp-...>...</dexp-...>
                # Используем более общий паттерн для любых тегов, начинающихся на <d...
                text = re.sub(r'<d[^>]*>.*?(</d[^>]*>|$)', '', text, flags=re.DOTALL).strip()
                # 3. Удаляем одиночные теги <d...> или <dexp...>
                text = re.sub(r'<d[^>]*>', '', text).strip()
                # 4. Удаляем системные префиксы если они остались
                text = re.sub(r'TEAM_PERSONALITIES\.MD:.*?\n\n', '', text, flags=re.DOTALL).strip()
                text = re.sub(r'### ТЫ — .*?\n', '', text, flags=re.DOTALL).strip()
                text = re.sub(r'### \[CRITICAL: ANTI-HALLUCINATION.*?\]', '', text, flags=re.DOTALL).strip()
                # 5. Финальная чистка от лишних пробелов и пустых строк в начале
                text = text.strip()

            if stream:
                # SSE streaming для OpenAI
                async def generate():
                    words = text.split()
                    for i, word in enumerate(words):
                        chunk = {
                            "id": f"{request_id}-{i}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": word + " "},
                                "finish_reason": None,
                            }],
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"
                        await asyncio.sleep(0.02)
                    # Final chunk
                    final = {
                        "id": request_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop",
                        }],
                    }
                    yield f"data: {json.dumps(final)}\n\n"
                    yield "data: [DONE]\n\n"
                
                return StreamingResponse(generate(), media_type="text/event-stream")
            
            return JSONResponse(
                content={
                    "id": request_id,
                    "object": "chat.completion",
                    "created": int(__import__("time").time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": text},
                        "finish_reason": "stop",
                    }],
                    "usage": {"prompt_tokens": 0, "completion_tokens": len(text.split()), "total_tokens": len(text.split())},
                }
            )
        except Exception as e:
            import traceback
            err_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"❌ [DISCUSS] Failed to generate team discussion: {err_msg}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Discussion engine error: {err_msg}")

    try:
        # Simple requests WITHOUT category to avoid timeout in Victoria container
        vic_response = await call_victoria_run(goal, request_id, chat_history=chat_history)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Victoria request timed out")
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"Victoria unreachable: {VICTORIA_URL}")

    status = vic_response.get("status", "")
    output = vic_response.get("output")
    if output is None and status != "success":
        if status == "needs_clarification":
            questions = vic_response.get("clarification_questions") or []
            restated = vic_response.get("suggested_restatement") or ""
            parts = ["Нужно уточнение."]
            if restated:
                parts.append(f"Уточнённая формулировка: {restated}")
            if questions:
                parts.append("Вопросы: " + "; ".join(q if isinstance(q, str) else q.get("text", str(q)) for q in questions))
            output = "\n".join(parts)
        else:
            output = vic_response.get("error") or f"Victoria status: {status}"
    text = str(output) if output is not None else ""
    
    # Сохраняем обмен в историю диалога
    if session_id not in _dialogue_store:
        _dialogue_store[session_id] = []
    _dialogue_store[session_id].append({"user": goal, "assistant": text})
    # Ограничиваем историю 50 обменами
    if len(_dialogue_store[session_id]) > 50:
        _dialogue_store[session_id] = _dialogue_store[session_id][-50:]

    return JSONResponse(
        content={
            "id": request_id,
            "object": "chat.completion",
            "created": int(__import__("time").time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": len(text.split()), "total_tokens": len(text.split())},
        }
    )
