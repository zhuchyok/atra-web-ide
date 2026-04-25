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
import uuid
import logging
from typing import Optional, AsyncGenerator, List

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# По умолчанию localhost:8010 (снаружи Docker), но в Rocket Mode может быть victoria-agent:8000
VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010").rstrip("/")
# Авто-определение: если мы в Docker и victoria-agent доступен, переключаемся
if os.path.exists("/.dockerenv") and VICTORIA_URL == "http://localhost:8010":
    VICTORIA_URL = "http://victoria-agent:8000"

VICTORIA_TIMEOUT = float(os.getenv("VICTORIA_PROXY_TIMEOUT", "600"))  # 10 мин для тяжёлых задач
# Префикс в ответе, чтобы в Claude Code было видно, что отвечает Виктория (модель под капотом может называться Qwen и т.д.)
VICTORIA_RESPONSE_PREFIX = os.getenv("VICTORIA_RESPONSE_PREFIX", "Виктория (корпорация): ").strip()

# Один одновременный запрос к Victoria — избегаем обрывов при 2+ параллельных от Claude Code
_victoria_semaphore = asyncio.Semaphore(1)

# Хранилище диалогов: session_id → [{"user": "...", "assistant": "..."}]
_dialogue_store: dict[str, list[dict]] = {}

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
async def call_victoria_run(goal: str, correlation_id: str, chat_history: Optional[List[dict]] = None) -> dict:
    """Вызов Victoria POST /run (синхронный режим). Возвращает dict с status и output.
    Семафор: не более одного запроса к Victoria одновременно — устраняет обрывы при 2+ параллельных от Claude Code.
    chat_history — список {"user": "...", "assistant": "..."} для контекста диалога."""
    payload = {"goal": goal}
    if chat_history:
        payload["chat_history"] = chat_history
    # X-Forwarded-For явно ставим в 127.0.0.1 — иначе Victoria видит GitHub CDN IP (185.199.x.x)
    # от Claude Code/OpenCode и считает его внешним клиентом (rate-limit/блокировка).
    headers = {"Content-Type": "application/json", "X-Correlation-ID": correlation_id, "X-Forwarded-For": "127.0.0.1"}
    timeout = httpx.Timeout(10.0, read=VICTORIA_TIMEOUT)
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
                if resp.status_code != 200:
                    logger.warning("Victoria /run returned %s: %s", resp.status_code, resp.text[:500])
                    raise HTTPException(
                        status_code=502,
                        detail=f"Victoria returned {resp.status_code}: {resp.text[:200]}",
                    )
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

    logger.info("[PROXY] goal_preview=%s session=%s", goal[:80], session_id)

    try:
        # Передаём историю в Victoria
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
