"""
Chat Router - SSE стриминг для AI чата (Singularity 14.0 Unified)
Прокси-роутер, передающий все запросы в Victoria Agent.
"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.metrics.prometheus_metrics import ASK_VICTORIA_TOTAL, CHAT_EXPERT_ANSWER_TOTAL
from app.metrics.prometheus_metrics import metrics as prometheus_metrics
from app.services.concurrency_limiter import (
    acquire_victoria_slot,
    release_victoria_slot,
    with_victoria_slot,
)
from app.services.conversation_context import get_conversation_context_manager
from app.services.ollama import OllamaClient, get_ollama_client
from app.services.knowledge_os import KnowledgeOSClient, get_knowledge_os_client
from app.services.victoria import VictoriaClient, get_victoria_client

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatMessage(BaseModel):
    """Сообщение в чат"""

    content: str = Field(..., min_length=1, max_length=10000)
    expert_name: Optional[str] = Field(default=None, max_length=100)
    model: Optional[str] = Field(default=None, max_length=100)
    use_victoria: bool = True
    mode: Optional[str] = Field(default="agent", description="agent | plan | ask — как в Cursor")
    user_id: Optional[str] = Field(default=None, max_length=128)
    session_id: Optional[str] = Field(default=None, max_length=128)
    domain: Optional[str] = Field(default=None, max_length=255)


class AIChatRequest(BaseModel):
    """Запрос для публичного AI чата дилера"""
    message: str
    domain: str
    session_id: Optional[str] = None


@router.post("/public/send")
async def send_public_message(
    request: AIChatRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
    knowledge_os: KnowledgeOSClient = Depends(get_knowledge_os_client)
):
    """
    Публичный эндпоинт для чата дилера.
    Использует локальный Ollama с контекстом конкретного дилера.
    """
    domain = request.domain.replace("www.", "")
    
    # 1. Получаем данные дилера из БД
    async with knowledge_os._pool.acquire() as conn:
        dealer = await conn.fetchrow(
            "SELECT name, city, phone, email, address, branding, margin_config FROM dealers WHERE domain = $1 OR domain = $2",
            domain, f"www.{domain}"
        )
    
    if not dealer:
        # Fallback на дефолтные настройки если домен не найден
        dealer_info = "Компания 'Сетки 21', производство москитных сеток."
    else:
        branding = json.loads(dealer.get("branding") or "{}")
        dealer_info = f"""
        Название: {dealer['name']}
        Город: {dealer['city']}
        Телефон: {dealer['phone']}
        Email: {dealer['email']}
        Адрес: {dealer['address']}
        Режим работы: {branding.get('working_hours', 'не указан')}
        """

    # 2. Получаем цены (динамически из БД)
    async with knowledge_os._pool.acquire() as conn:
        products_rows = await conn.fetch(
            "SELECT name, price_config FROM products WHERE is_active = true"
        )
    
    prices_info = ""
    for p in products_rows:
        p_config = json.loads(p.get("price_config") or "{}")
        # Для клиента показываем dealer_price как базовую "от"
        price = p_config.get("dealer_price", 0)
        if price > 0:
            prices_info += f"- {p['name']}: от {price} руб.\n"

    # 3. Формируем системный промпт
    system_prompt = f"""
    Ты — умный ассистент компании по производству москитных сеток.
    Твоя цель: помогать клиентам, отвечать на вопросы о сетках и мягко подводить к заказу.
    
    ИНФОРМАЦИЯ О ТЕКУЩЕМ ДИЛЕРЕ:
    {dealer_info}
    
    АКТУАЛЬНЫЕ ЦЕНЫ:
    {prices_info if prices_info else "- Уточняйте у менеджера"}
    (Цены могут меняться в зависимости от размера, уточни у менеджера).
    
    СТИЛЬ ОБЩЕНИЯ:
    - Вежливый, профессиональный, лаконичный.
    - Используй только русский язык.
    - Если клиент хочет заказать, попроси его оставить телефон или воспользоваться калькулятором на сайте.
    
    ОГРАНИЧЕНИЯ:
    - Не выдумывай несуществующие услуги.
    - Если не знаешь ответа, предложи связаться по телефону {dealer['phone'] if dealer else 'указанному на сайте'}.
    """

    # 4. Вызов Ollama
    try:
        response = await ollama.generate(
            prompt=request.message,
            model="qwen2.5:0.5b",
            system=system_prompt
        )
        return {"content": response.get("response", "Извините, я временно не могу ответить.")}
    except Exception as e:
        logger.error(f"Ollama public chat error: {e}")
        return {"content": "Произошла ошибка при обращении к ИИ. Пожалуйста, попробуйте позже."}


class ChatResponse(BaseModel):
    """Ответ от чата"""

    content: str
    expert_name: Optional[str] = None
    model: Optional[str] = None


class AskVictoriaRequest(BaseModel):
    """Запрос для инструмента ask_victoria (Singularity 15.0)"""

    goal: str = Field(..., min_length=1, max_length=50000)
    project_context: Optional[str] = Field(default="atra-web-ide", max_length=128)
    user_key: Optional[str] = Field(
        default=None, max_length=256, description="Stable user id e.g. openwebui-{user_id} for LTM"
    )
    chat_history: Optional[List[Dict[str, str]]] = Field(
        default=None, description="History as [{user, assistant}, ...] for Victoria context"
    )


@router.post("/send", response_model=ChatResponse)
async def send_message(
    message: ChatMessage, victoria: VictoriaClient = Depends(get_victoria_client)
) -> ChatResponse:
    """Отправить сообщение (не-стриминг) — прокси к Victoria /run"""
    try:
        acquired = await acquire_victoria_slot()
        if not acquired:
            return JSONResponse(
                status_code=503,
                content={"error": "service_busy", "detail": "Too many concurrent requests."},
                headers={"Retry-After": "60"},
            )

        correlation_id = str(uuid.uuid4())
        session_id = message.session_id or message.user_id

        chat_history = []
        if session_id:
            ctx_mgr = get_conversation_context_manager()
            # [OPTIMIZATION] Get recent messages with character limit directly in get_recent
            recent = await ctx_mgr.get_recent(session_id, last_n=10, max_chars=10000)
            chat_history = ctx_mgr.to_victoria_chat_history(recent)

        result = await victoria.run(
            prompt=message.content,
            expert_name=message.expert_name,
            session_id=session_id,
            chat_history=chat_history,
            correlation_id=correlation_id,
        )

        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error"))

        content = result.get("result", "") or result.get("response", "")

        # Сохраняем контекст
        if session_id:
            ctx_mgr = get_conversation_context_manager()
            await ctx_mgr.append(session_id, "user", message.content)
            await ctx_mgr.append(session_id, "assistant", content)

        CHAT_EXPERT_ANSWER_TOTAL.labels(source="victoria_unified").inc()

        return ChatResponse(
            content=content, expert_name=message.expert_name, model=result.get("model")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat send error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_victoria_slot()


@router.post("/stream")
@prometheus_metrics.track_request(mode="stream", endpoint="stream")
async def stream_message(
    message: ChatMessage, victoria: VictoriaClient = Depends(get_victoria_client)
):
    """SSE стриминг ответа (Singularity 14.0 Unified) — прокси к Victoria /stream"""
    acquired = await acquire_victoria_slot()
    if not acquired:
        return JSONResponse(
            status_code=503,
            content={"error": "service_busy", "detail": "Too many concurrent requests."},
            headers={"Retry-After": "60"},
        )

    correlation_id = str(uuid.uuid4())
    session_id = message.session_id or message.user_id

    chat_history = []
    if session_id:
        ctx_mgr = get_conversation_context_manager()
        # [OPTIMIZATION] Use built-in character limit in get_recent
        recent = await ctx_mgr.get_recent(session_id, last_n=10, max_chars=10000)
        chat_history = ctx_mgr.to_victoria_chat_history(recent)

    async def proxy_generator():
        full_response = []
        try:
            async for line in victoria.run_stream(
                prompt=message.content,
                expert_name=message.expert_name,
                session_id=session_id,
                chat_history=chat_history,
                correlation_id=correlation_id,
                mode=message.mode or "agent",
            ):
                yield line + "\n\n"
                # Пытаемся извлечь контент для сохранения в историю
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        if data.get("type") == "chunk":
                            full_response.append(data.get("content", ""))
                    except:
                        pass

            # Сохраняем историю после завершения стрима
            if session_id and full_response:
                ctx_mgr = get_conversation_context_manager()
                # [OPTIMIZATION] Batch append to reduce DB/Redis calls
                await asyncio.gather(
                    ctx_mgr.append(session_id, "user", message.content),
                    ctx_mgr.append(session_id, "assistant", "".join(full_response)),
                )

        except asyncio.CancelledError:
            logger.info(f"Stream cancelled by client for session {session_id}")
            # [OPTIMIZATION] Still try to save partial response if cancelled
            if session_id and full_response:
                try:
                    ctx_mgr = get_conversation_context_manager()
                    await ctx_mgr.append(
                        session_id, "assistant", "".join(full_response) + " [cancelled]"
                    )
                except:
                    pass
            raise
        except Exception as e:
            logger.error("Stream error for session %s: %s", session_id, e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'end'})}\n\n"
        finally:
            release_victoria_slot()

    return StreamingResponse(
        proxy_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/ask-victoria")
async def ask_victoria(
    body: AskVictoriaRequest,
    victoria: VictoriaClient = Depends(get_victoria_client),
    format: Optional[str] = Query(None, description="Response format: json for JSON body"),
):
    """
    Singularity 15.0: единая точка делегирования в Victoria.
    Для Open WebUI: вызов этого endpoint как инструмента ask_victoria.
    Возвращает текст ответа или сообщение о недоступности Victoria.
    ?format=json — ответ в виде JSON: { "status": "success"|"error", "result": "..." }.
    """
    goal_stripped = (body.goal or "").strip()
    if not goal_stripped:
        if format == "json":
            return JSONResponse(
                status_code=422,
                content={"status": "error", "result": "goal is required and cannot be empty"},
            )
        return PlainTextResponse("goal is required and cannot be empty", status_code=422)

    acquired = await acquire_victoria_slot()
    if not acquired:
        ASK_VICTORIA_TOTAL.labels(status="busy").inc()
        if format == "json":
            return JSONResponse(
                status_code=503,
                content={"status": "error", "result": "Too many requests; try again later."},
                headers={"Retry-After": "60"},
            )
        return PlainTextResponse(
            "Too many requests; try again later.", status_code=503, headers={"Retry-After": "60"}
        )

    session_id = body.user_key or str(uuid.uuid4())

    def _user_facing_error(err: str) -> str:
        """Короткое сообщение для пользователя/LLM без утечки внутренних деталей."""
        if not err:
            return "Victoria временно недоступна; попробуйте через минуту."
        e = err.lower()
        if "task lost" in e or "restarted" in e:
            return "Задача потеряна (Victoria могла перезапуститься). Пожалуйста, повторите запрос."
        if "timeout" in e or "timed out" in e:
            return "Victoria не успела ответить (таймаут). Задача сложная или сервер перегружен — попробуйте через минуту или упростите запрос."
        if "connect" in e or "refused" in e or "name or service not known" in e:
            return "Victoria недоступна (нет связи с сервисом). Убедитесь, что Victoria запущена (порт 8010 / victoria-agent)."
        if "503" in e or "502" in e or "500" in e:
            return "Victoria временно перегружена или вернула ошибку; попробуйте через минуту."
        return "Victoria временно недоступна; попробуйте через минуту."

    try:
        result = await victoria.run(
            prompt=goal_stripped,
            project_context=(body.project_context or "atra-web-ide").strip(),
            session_id=session_id,
            chat_history=body.chat_history,
            use_enhanced=True,
        )
        if result.get("status") == "error":
            ASK_VICTORIA_TOTAL.labels(status="error").inc()
            err_detail = result.get("error") or ""
            msg = _user_facing_error(err_detail)
            logger.warning(
                "ask_victoria Victoria returned error: %s",
                err_detail[:200] if err_detail else "no detail",
            )
            if format == "json":
                return JSONResponse(status_code=503, content={"status": "error", "result": msg})
            return PlainTextResponse(msg, status_code=503)
        content = result.get("result", "") or result.get("response", "") or ""
        if not isinstance(content, str):
            content = str(content)
        clarification = result.get("clarification_questions")
        if clarification:
            if isinstance(clarification, list):
                lines = [
                    f"Мне нужно уточнить: {q}" if isinstance(q, str) else str(q)
                    for q in clarification
                ]
                content = "\n".join(lines) + ("\n\n" + content if content else "")
            else:
                content = str(clarification) + ("\n\n" + content if content else "")
        ASK_VICTORIA_TOTAL.labels(status="success").inc()
        if format == "json":
            return JSONResponse(content={"status": "success", "result": content})
        return PlainTextResponse(content)
    except Exception as e:
        logger.warning("ask_victoria error: %s", e)
        ASK_VICTORIA_TOTAL.labels(status="error").inc()
        msg = _user_facing_error(str(e))
        if format == "json":
            return JSONResponse(status_code=503, content={"status": "error", "result": msg})
        return PlainTextResponse(msg, status_code=503)
    finally:
        release_victoria_slot()


@router.get("/status")
async def chat_status(victoria: VictoriaClient = Depends(get_victoria_client)) -> dict:
    """Статус Victoria"""
    return await victoria.health()


@router.get("/models")
async def list_models(victoria: VictoriaClient = Depends(get_victoria_client)) -> dict:
    """Список моделей через Victoria"""
    return await victoria.status()


@router.get("/hidden-thoughts/{session_id}")
async def get_hidden_thoughts(
    session_id: str, victoria: VictoriaClient = Depends(get_victoria_client)
):
    """Получить скрытые рассуждения для сессии (Summary Reader)"""
    try:
        # Проксируем запрос к Victoria Agent
        # Victoria Agent должен иметь endpoint /api/hidden-thoughts/{session_id}
        result = await victoria.get_hidden_thoughts(session_id)
        return result
    except Exception as e:
        logger.error(f"Error fetching hidden thoughts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
