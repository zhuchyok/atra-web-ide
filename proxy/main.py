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
import re
from typing import Optional, AsyncGenerator, List

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
import asyncio
from collections import defaultdict

try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
except ImportError:
    Counter = None
    Histogram = None
    generate_latest = None
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010").rstrip("/")
# Авто-определение: если мы в Docker и victoria-agent доступен, переключаемся
if os.path.exists("/.dockerenv") and VICTORIA_URL == "http://localhost:8010":
    VICTORIA_URL = "http://victoria-agent:8000"

VICTORIA_TIMEOUT = float(os.getenv("VICTORIA_PROXY_TIMEOUT", "60"))  # bounded latency for regular requests
VICTORIA_MAX_ATTEMPTS = int(os.getenv("VICTORIA_PROXY_MAX_ATTEMPTS", "2"))
VICTORIA_HEALTH_TIMEOUT = float(os.getenv("VICTORIA_PROXY_HEALTH_TIMEOUT", "15"))
DISCUSS_TIMEOUT = float(os.getenv("VICTORIA_DISCUSS_TIMEOUT", "240"))
PROXY_TOTAL_TIMEOUT = float(os.getenv("PROXY_TOTAL_TIMEOUT", "75"))
DISCUSS_TOTAL_TIMEOUT = float(os.getenv("PROXY_DISCUSS_TOTAL_TIMEOUT", "90"))
# Префикс в ответе, чтобы в Claude Code было видно, что отвечает Виктория (модель под капотом может называться Qwen и т.д.)
VICTORIA_RESPONSE_PREFIX = os.getenv("VICTORIA_RESPONSE_PREFIX", "Виктория (корпорация): ").strip()

# Multiple parallel requests OK
_victoria_semaphore = asyncio.Semaphore(10)

# Хранилище диалогов: session_id → [{"user": "...", "assistant": "..."}]
_dialogue_store: dict[str, list[dict]] = {}

# [SINGULARITY 10.0] Support for 'discuss' model - Team Discussion Engine
import sys

# --- Proxy metrics (Prometheus + local summary fallback) ---
_metrics_fallback = {
    "requests_total": defaultdict(int),
    "sanitize_hits_total": defaultdict(int),
    "latency_count": defaultdict(int),
    "latency_sum_sec": defaultdict(float),
}

if Counter is not None and Histogram is not None:
    _proxy_requests_total = Counter(
        "proxy_requests_total",
        "Total proxy chat completion requests",
        ["model", "status"],
    )
    _proxy_sanitize_hits_total = Counter(
        "proxy_sanitize_hits_total",
        "Number of responses modified by output sanitizer",
        ["model"],
    )
    _proxy_latency_seconds = Histogram(
        "proxy_latency_seconds",
        "Proxy request latency in seconds",
        ["model"],
    )
else:
    _proxy_requests_total = None
    _proxy_sanitize_hits_total = None
    _proxy_latency_seconds = None

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


def sanitize_output(text: str) -> tuple[str, bool]:
    """
    Удаляет служебные reasoning/think теги и системные заголовки.
    Возвращает (очищенный_текст, modified_flag).
    """
    if not text:
        return "", False

    cleaned = str(text)
    original = cleaned
    # Removes hidden reasoning blocks often returned by local models.
    cleaned = re.sub(r"<think>.*?(</think>|$)", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<details[^>]*>.*?</details>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<summary[^>]*>.*?</summary>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    # Removes dexp/debug style tags.
    cleaned = re.sub(r"<d[^>]*>.*?(</d[^>]*>|$)", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<d[^>]*>", "", cleaned, flags=re.IGNORECASE)
    # Removes meta "final sequence" noise occasionally emitted by local model.
    cleaned = re.sub(
        r"Done!? ?Executing Final Sequence NOW!?[!\.\s]*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"Final Output Delivered Now!?[!\.\s]*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Removes reasoning/process artifacts in plain text.
    cleaned = re.sub(r"\[Процесс объяснения:.*", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"\(End of thought process\).*", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"Thought for \d+ seconds.*", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    # Removes known system preambles.
    cleaned = re.sub(r"TEAM_PERSONALITIES\.MD:.*?\n\n", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"### ТЫ — .*?\n", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"### \[CRITICAL: ANTI-HALLUCINATION.*?\]", "", cleaned, flags=re.DOTALL)
    # Normalize whitespace.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, cleaned != original


def is_degraded_output(text: str) -> bool:
    """
    Detects low-quality corrupted outputs (punctuation spam, almost no letters).
    """
    if not text:
        return True

    sample = text.strip()
    if len(sample) < 20:
        return False
    if sample.startswith("⚠️ Модель вернула поврежденный ответ") or sample.startswith(
        "⚠️ Модель вернула повреждённый ответ"
    ):
        return True

    punctuation_count = len(re.findall(r"[!?]{2,}", sample))
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", sample)
    letter_ratio = (len(letters) / len(sample)) if sample else 0.0

    # Heuristic: many punctuation bursts + very low letter density.
    if punctuation_count >= 10 and letter_ratio < 0.35:
        return True
    return False


def _observe_metrics(model: str, status: str, latency_sec: float, sanitized: bool) -> None:
    """Updates Prometheus metrics and a local fallback summary."""
    model_key = model or "unknown"
    status_key = status or "unknown"

    _metrics_fallback["requests_total"][(model_key, status_key)] += 1
    _metrics_fallback["latency_count"][model_key] += 1
    _metrics_fallback["latency_sum_sec"][model_key] += max(0.0, latency_sec)
    if sanitized:
        _metrics_fallback["sanitize_hits_total"][model_key] += 1

    if _proxy_requests_total is not None:
        _proxy_requests_total.labels(model=model_key, status=status_key).inc()
    if _proxy_latency_seconds is not None:
        _proxy_latency_seconds.labels(model=model_key).observe(max(0.0, latency_sec))
    if sanitized and _proxy_sanitize_hits_total is not None:
        _proxy_sanitize_hits_total.labels(model=model_key).inc()


# --- Victoria: POST /run → TaskResponse ---
async def call_victoria_run(
    goal: str,
    correlation_id: str,
    chat_history: Optional[List[dict]] = None,
    category: Optional[str] = None,
    timeout_sec: Optional[float] = None,
    max_attempts: Optional[int] = None,
) -> dict:
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

    # Используем переданный таймаут или глобальный
    current_timeout = timeout_sec or VICTORIA_TIMEOUT
    timeout = httpx.Timeout(current_timeout, connect=10.0, read=current_timeout - 10.0)
    last_error = None
    attempts = max(1, max_attempts or VICTORIA_MAX_ATTEMPTS)
    async with _victoria_semaphore:
        for attempt in range(attempts):
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
            except (
                httpx.RemoteProtocolError,
                httpx.ReadError,
                httpx.ConnectError,
                httpx.TimeoutException,
            ) as e:
                last_error = e
                logger.warning(
                    "Victoria connection error (attempt %s/%s, correlation_id=%s): %s [%s]",
                    attempt + 1,
                    attempts,
                    correlation_id,
                    (e.args[0] if e.args else ""),
                    type(e).__name__,
                )
                if attempt < attempts - 1:
                    await asyncio.sleep(2.0 * (attempt + 1))
                continue
    logger.error(
        "Victoria unreachable after %s attempts: %s [%s]",
        attempts,
        last_error,
        type(last_error).__name__ if last_error else "?",
    )
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
    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=VICTORIA_HEALTH_TIMEOUT) as client:
            vic_resp = await client.get(f"{VICTORIA_URL}/health")
            victoria_ok = vic_resp.status_code == 200
            victoria_status_code = vic_resp.status_code
    except Exception:
        victoria_ok = False
        victoria_status_code = None

    return JSONResponse(content={
        "status": "ok",
        "proxy": "anthropic-victoria",
        "victoria_url": VICTORIA_URL,
        "victoria_reachable": victoria_ok,
        "victoria_status_code": victoria_status_code,
        "victoria_health_timeout_sec": VICTORIA_HEALTH_TIMEOUT,
        "latency_ms": int((time.time() - started) * 1000),
    })


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint for proxy observability."""
    if generate_latest is None:
        lines = [
            "# proxy metrics fallback (prometheus_client is not installed)",
            f'proxy_requests_total {sum(_metrics_fallback["requests_total"].values())}',
        ]
        return StreamingResponse(iter(["\n".join(lines)]), media_type=CONTENT_TYPE_LATEST)
    payload = generate_latest()
    return StreamingResponse(iter([payload]), media_type=CONTENT_TYPE_LATEST)


@app.get("/metrics/summary")
async def metrics_summary():
    """Lightweight JSON summary for quick smoke checks."""
    requests_by_model = defaultdict(lambda: {"success": 0, "error": 0, "total": 0})
    for (model, status), count in _metrics_fallback["requests_total"].items():
        requests_by_model[model]["total"] += count
        if status == "success":
            requests_by_model[model]["success"] += count
        else:
            requests_by_model[model]["error"] += count

    latency_avg = {}
    for model, count in _metrics_fallback["latency_count"].items():
        total = _metrics_fallback["latency_sum_sec"][model]
        latency_avg[model] = round(total / count, 4) if count else 0.0

    return JSONResponse(
        content={
            "requests_by_model": requests_by_model,
            "sanitize_hits_by_model": dict(_metrics_fallback["sanitize_hits_total"]),
            "latency_avg_sec_by_model": latency_avg,
        }
    )


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

    started = time.time()
    logger.info("[PROXY] goal_preview=%s session=%s model=%s", goal[:80], session_id, model)
    logger.info("[PROXY] calling Victoria...")

    # Fast-path for simple greetings: avoids unnecessary heavy orchestration path.
    goal_norm = goal.strip().lower()
    if goal_norm in {"привет", "здравствуй", "hello", "hi", "hey"}:
        text = "Привет! Я Виктория, Team Lead корпорации ATRA. Чем могу помочь?"
        _observe_metrics(model=model, status="success", latency_sec=(time.time() - started), sanitized=False)
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

    # [SINGULARITY 10.0] Support for 'discuss' model - Team Discussion Engine
    if model in ("discuss", "victoria-discuss"):
        try:
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
            # Simple call without category override, but with increased timeout
            vic_response = await asyncio.wait_for(
                call_victoria_run(
                    discussion_prompt,
                    request_id,
                    chat_history=chat_history,
                    timeout_sec=min(DISCUSS_TIMEOUT, DISCUSS_TOTAL_TIMEOUT - 5),
                    max_attempts=1,
                ),
                timeout=DISCUSS_TOTAL_TIMEOUT,
            )
            logger.info("[PROXY] got Victoria response, status=%s", vic_response.get("status"))

            # [SINGULARITY 10.13] Фикс: если Victoria вернула ошибку таймаута,
            # мы можем предложить пользователю подождать или использовать другую модель.
            status = vic_response.get("status", "")
            output = vic_response.get("output")

            # [SINGULARITY 10.17] ДИАГНОСТИКА: Логируем сырой ответ от Victoria
            logger.info("[PROXY] Raw Victoria output preview: %s", str(output)[:100])

            # [SINGULARITY 29.6] ФИКС: Если output пустой, но статус success,
            # значит что-то пошло не так в Victoria.
            if not output and status == "success":
                logger.warning("[PROXY] Victoria returned success but empty output")
                output = "⚠️ Ошибка: модель вернула пустой ответ. Попробуйте еще раз."

            if not output:
                output = vic_response.get("error") or f"Status: {status}"

            if status == "failed" and "timeout" in str(vic_response.get("knowledge", {}).get("error", "")):
                output = "⚠️ **Локальная модель (Wisdom 35B) перегружена.**\n\nГенерация диалога заняла более 5 минут. Это обычно происходит, когда Mac Studio выполняет другие тяжелые задачи (например, воркеры обучают модели или индексируют файлы).\n\n**Что можно сделать:**\n1. Попробуйте отправить запрос еще раз через минуту.\n2. Убедитесь, что в системе нет зависших тяжелых процессов."

            text = str(output)

            text, sanitized = sanitize_output(text)
            if is_degraded_output(text):
                logger.warning("[PROXY] discuss output degraded, fallback to regular Victoria mode")
                try:
                    fallback_response = await asyncio.wait_for(
                        call_victoria_run(
                            goal=goal,
                            correlation_id=f"{request_id}-fallback",
                            chat_history=chat_history,
                            timeout_sec=max(20.0, PROXY_TOTAL_TIMEOUT - 5),
                            max_attempts=1,
                        ),
                        timeout=PROXY_TOTAL_TIMEOUT,
                    )
                    fallback_text = str(
                        fallback_response.get("output")
                        or fallback_response.get("error")
                        or ""
                    )
                    fallback_text, fallback_sanitized = sanitize_output(fallback_text)
                    if fallback_text and not is_degraded_output(fallback_text):
                        text = fallback_text
                        sanitized = True or fallback_sanitized
                    else:
                        text = "⚠️ Модель вернула поврежденный ответ. Повторите запрос еще раз — система автоматически восстановит контекст."
                        sanitized = True
                except Exception as fallback_exc:
                    logger.warning("[PROXY] discuss fallback failed: %s", fallback_exc)
                    text = "⚠️ Модель вернула поврежденный ответ. Повторите запрос еще раз — система автоматически восстановит контекст."
                    sanitized = True

            # Проверяем stream parameter
            stream = body.get("stream", False)

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

                _observe_metrics(model=model, status="success", latency_sec=(time.time() - started), sanitized=sanitized)
                return StreamingResponse(generate(), media_type="text/event-stream")

            _observe_metrics(model=model, status="success", latency_sec=(time.time() - started), sanitized=sanitized)
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
        except HTTPException:
            _observe_metrics(model=model, status="error", latency_sec=(time.time() - started), sanitized=False)
            raise
        except Exception as e:
            import traceback
            err_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"❌ [DISCUSS] Failed to generate team discussion: {err_msg}")
            logger.error(traceback.format_exc())
            _observe_metrics(model=model, status="error", latency_sec=(time.time() - started), sanitized=False)
            raise HTTPException(status_code=500, detail=f"Discussion engine error: {err_msg}")

    try:
        # Simple requests WITHOUT category to avoid timeout in Victoria container
        vic_response = await asyncio.wait_for(
            call_victoria_run(
                goal,
                request_id,
                chat_history=chat_history,
                timeout_sec=max(20.0, PROXY_TOTAL_TIMEOUT - 5),
                max_attempts=1,
            ),
            timeout=PROXY_TOTAL_TIMEOUT,
        )
    except asyncio.TimeoutError:
        _observe_metrics(model=model, status="error", latency_sec=(time.time() - started), sanitized=False)
        raise HTTPException(status_code=504, detail="Proxy total timeout while waiting for Victoria")
    except httpx.TimeoutException:
        _observe_metrics(model=model, status="error", latency_sec=(time.time() - started), sanitized=False)
        raise HTTPException(status_code=504, detail="Victoria request timed out")
    except httpx.ConnectError as e:
        _observe_metrics(model=model, status="error", latency_sec=(time.time() - started), sanitized=False)
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
    text, sanitized = sanitize_output(text)
    if is_degraded_output(text):
        text = "⚠️ Модель вернула поврежденный ответ. Повторите запрос еще раз — система автоматически восстановит контекст."
        sanitized = True

    # Сохраняем обмен в историю диалога
    if session_id not in _dialogue_store:
        _dialogue_store[session_id] = []
    _dialogue_store[session_id].append({"user": goal, "assistant": text})
    # Ограничиваем историю 50 обменами
    if len(_dialogue_store[session_id]) > 50:
        _dialogue_store[session_id] = _dialogue_store[session_id][-50:]

    _observe_metrics(model=model, status="success", latency_sec=(time.time() - started), sanitized=sanitized)
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
