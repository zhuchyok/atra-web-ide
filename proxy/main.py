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
from typing import Optional, AsyncGenerator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

logger = logging.getLogger(__name__)

VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010").rstrip("/")
VICTORIA_TIMEOUT = float(os.getenv("VICTORIA_PROXY_TIMEOUT", "600"))  # 10 мин для тяжёлых задач
# Префикс в ответе, чтобы в Claude Code было видно, что отвечает Виктория (модель под капотом может называться Qwen и т.д.)
VICTORIA_RESPONSE_PREFIX = os.getenv("VICTORIA_RESPONSE_PREFIX", "Виктория (корпорация): ").strip()

# Один одновременный запрос к Victoria — избегаем обрывов при 2+ параллельных от Claude Code
_victoria_semaphore = asyncio.Semaphore(1)

app = FastAPI(
    title="Claude Code → Victoria Proxy",
    description="Anthropic Messages API compatible proxy to Victoria (experts, orchestrators)",
    version="1.0.0",
)


# --- Anthropic request: messages[] with role/content ---


def _extract_last_user_text(messages: list[dict]) -> str:
    """Из списка messages (сырой JSON) берём последнее сообщение пользователя (role=user) и извлекаем текст."""
    for m in reversed(messages):
        if m.get("role") != "user":
            continue
        content = m.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text" and "text" in block:
                    parts.append(block["text"])
            if parts:
                return "\n".join(parts).strip()
    return ""


# --- Victoria: POST /run → TaskResponse ---
async def call_victoria_run(goal: str, correlation_id: str) -> dict:
    """Вызов Victoria POST /run (синхронный режим). Возвращает dict с status и output.
    Семафор: не более одного запроса к Victoria одновременно — устраняет обрывы при 2+ параллельных от Claude Code."""
    payload = {"goal": goal}
    headers = {"Content-Type": "application/json", "X-Correlation-ID": correlation_id}
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
            "usage": {"input_tokens": 0, "output_tokens": 0},
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
            "output_tokens": max(0, len((text or "").split())),  # приблизительно
        },
    }


@app.post("/v1/messages/count_tokens")
async def count_tokens(request: Request):
    """
    Anthropic count_tokens: клиент (Claude Code) дергает перед отправкой.
    Возвращаем приблизительное число токенов, чтобы не было 404.
    """
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    messages_list = body.get("messages") or []
    total_chars = 0
    for m in messages_list:
        content = m.get("content", "") if isinstance(m, dict) else ""
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    total_chars += len(str(block["text"]))
    # ~4 символа на токен для английского/смешанного текста
    input_tokens = max(1, total_chars // 4)
    return JSONResponse(content={"input_tokens": input_tokens}, status_code=200)


@app.get("/health")
async def health():
    """Проверка живости прокси и доступности Victoria."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{VICTORIA_URL}/health")
        vic_ok = r.status_code == 200
    except Exception as e:
        logger.debug("Victoria health check failed: %s", e)
        vic_ok = False
    return {
        "status": "ok",
        "proxy": "anthropic-victoria",
        "victoria_url": VICTORIA_URL,
        "victoria_reachable": vic_ok,
    }


@app.post("/v1/messages")
async def messages(request: Request):
    """
    Anthropic Messages API: принимаем запрос, переводим в Victoria /run, возвращаем в формате Anthropic.
    """
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    messages_list = body.get("messages") or []
    if not messages_list:
        raise HTTPException(status_code=400, detail="messages is required and must be non-empty")

    # Список может быть из dict (JSON)
    messages_as_dicts = [
        m if isinstance(m, dict) else {"role": getattr(m, "role", "user"), "content": getattr(m, "content", "")}
        for m in messages_list
    ]
    goal = _extract_last_user_text(messages_as_dicts)
    if not goal:
        raise HTTPException(status_code=400, detail="No user message text found in messages")

    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    request_id = f"msg_{uuid.uuid4().hex[:24]}"
    model = body.get("model")

    logger.info("[PROXY] goal_preview=%s correlation_id=%s", goal[:80], correlation_id)

    try:
        vic_response = await call_victoria_run(goal, correlation_id)
    except httpx.TimeoutException:
        logger.warning("[PROXY] Victoria timeout")
        raise HTTPException(status_code=504, detail="Victoria request timed out")
    except httpx.ConnectError as e:
        logger.warning("[PROXY] Victoria unreachable: %s", e)
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
    if VICTORIA_RESPONSE_PREFIX and text and not text.strip().startswith("Виктория"):
        text = VICTORIA_RESPONSE_PREFIX + text

    # Стриминг для Claude Code: при stream=true возвращаем SSE в формате Anthropic
    if body.get("stream") is True:
        logger.info("[PROXY] streaming response (Anthropic SSE)")
        return StreamingResponse(
            stream_anthropic_sse(text, request_id, model),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return JSONResponse(
        content=build_anthropic_response(text, request_id, model),
        status_code=200,
    )
