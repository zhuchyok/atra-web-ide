"""
Chat Router - SSE стриминг для AI чата (Singularity 10.0 Unified)
Прокси-роутер, передающий все запросы в Victoria Agent.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, AsyncGenerator
import json
import logging
import uuid

from app.services.victoria import VictoriaClient, get_victoria_client
from app.services.knowledge_os import KnowledgeOSClient, get_knowledge_os_client
from app.services.conversation_context import get_conversation_context_manager
from app.services.concurrency_limiter import acquire_victoria_slot, release_victoria_slot, with_victoria_slot
from app.metrics.prometheus_metrics import metrics as prometheus_metrics, CHAT_EXPERT_ANSWER_TOTAL

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

class ChatResponse(BaseModel):
    """Ответ от чата"""
    content: str
    expert_name: Optional[str] = None
    model: Optional[str] = None

@router.post("/send", response_model=ChatResponse)
async def send_message(
    message: ChatMessage,
    victoria: VictoriaClient = Depends(get_victoria_client)
) -> ChatResponse:
    """Отправить сообщение (не-стриминг) — прокси к Victoria /run"""
    try:
        correlation_id = str(uuid.uuid4())
        session_id = message.session_id or message.user_id
        
        chat_history = []
        if session_id:
            ctx_mgr = get_conversation_context_manager()
            recent = await ctx_mgr.get_recent(session_id, last_n=10)
            chat_history = ctx_mgr.to_victoria_chat_history(recent)

        result = await victoria.run(
            prompt=message.content,
            expert_name=message.expert_name,
            session_id=session_id,
            chat_history=chat_history,
            correlation_id=correlation_id
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
            content=content,
            expert_name=message.expert_name,
            model=result.get("model")
        )
    except Exception as e:
        logger.error(f"Chat send error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream")
@prometheus_metrics.track_request(mode="stream", endpoint="stream")
async def stream_message(
    message: ChatMessage,
    victoria: VictoriaClient = Depends(get_victoria_client)
):
    """SSE стриминг ответа (Singularity 10.0 Unified) — прокси к Victoria /stream"""
    acquired = await acquire_victoria_slot()
    if not acquired:
        return JSONResponse(
            status_code=503,
            content={"error": "service_busy", "detail": "Too many concurrent requests."},
            headers={"Retry-After": "60"}
        )

    correlation_id = str(uuid.uuid4())
    session_id = message.session_id or message.user_id
    
    chat_history = []
    if session_id:
        ctx_mgr = get_conversation_context_manager()
        recent = await ctx_mgr.get_recent(session_id, last_n=10)
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
                mode=message.mode or "agent"
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
                await ctx_mgr.append(session_id, "user", message.content)
                await ctx_mgr.append(session_id, "assistant", "".join(full_response))
                
        finally:
            release_victoria_slot()

    return StreamingResponse(
        proxy_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

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
    session_id: str,
    victoria: VictoriaClient = Depends(get_victoria_client)
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
