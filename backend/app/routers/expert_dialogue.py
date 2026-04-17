"""
Expert Dialogue Router - API для локальных диалогов экспертов
SINGULARITY 24.4 - Unified Expert Dialogue System

Поддерживает:
- Expert Council (последовательный мозговой штурм)
- Multi-Agent Debate (многоканальный спор)
- Collective Brainstorming (5-фазное проектирование)

Интеграция с Victoria для финального синтеза решений.
"""

import logging
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.victoria import VictoriaClient, get_victoria_client

logger = logging.getLogger(__name__)
router = APIRouter()


class DialogueMode(str, Enum):
    """Режим диалога"""

    SEQUENTIAL = "sequential"  # ExpertCouncil - последовательный
    DEBATE = "debate"  # MultiAgentDebate - многоканальный
    COLLABORATION = "collaboration"  # CollectiveBrainstorming - фазы
    SWARM = "swarm"  # Swarm Intelligence - роение


class DialogueRequest(BaseModel):
    """Запрос на диалог экспертов"""

    topic: str = Field(..., min_length=1, max_length=5000, description="Тема обсуждения")
    initial_proposal: Optional[str] = Field(
        None, max_length=10000, description="Начальное предложение"
    )
    mode: DialogueMode = Field(default=DialogueMode.DEBATE, description="Режим диалога")
    expert_ids: Optional[list[str]] = Field(None, description="Конкретные эксперты")
    round_limit: int = Field(default=3, ge=1, le=10, description="Лимит раундов")
    beautiful_mode: bool = Field(default=True, description="Использовать персоны")
    stream: bool = Field(default=False, description="SSE стриминг")


class ExpertOpinion(BaseModel):
    """Мнение эксперта"""

    expert_name: str
    opinion: str
    round: int = 1


class DialogueResponse(BaseModel):
    """Ответ диалога"""

    session_id: str
    topic: str
    mode: str
    participants: list[str]
    opinions: list[ExpertOpinion]
    final_decision: str
    consensus_score: Optional[float] = None
    status: str = "completed"
    victoria_synthesis: Optional[str] = None
    synthesis_by_victoria: bool = False


class DialogueStatus(BaseModel):
    """Статус диалога"""

    session_id: str
    status: str  # pending, in_progress, completed, failed
    progress: float = 0.0
    current_round: int = 1
    participants: list[str] = []


_sessions: dict[str, dict[str, Any]] = {}


async def _run_expert_council(topic: str, initial_proposal: str, beautiful: bool) -> dict:
    """Запуск ExpertCouncil диалога"""
    try:
        from knowledge_os.app.expert_council_discussion import ExpertCouncil

        council = ExpertCouncil()
        result = await council.start_debate(topic, initial_proposal, beautiful_mode=beautiful)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"ExpertCouncil failed: {e}")
        return {"success": False, "error": str(e)}


async def _run_multi_agent_debate(topic: str, initial: str, rounds: int) -> dict:
    """Запуск MultiAgentDebate"""
    try:
        from knowledge_os.app.multi_agent_debate import MultiAgentDebate

        debate = MultiAgentDebate()
        result = await debate.run_debate(topic, context=initial, rounds=rounds)
        return {
            "success": True,
            "result": {
                "topic": topic,
                "debate_history": result.debate_history
                if hasattr(result, "debate_history")
                else str(result),
                "final_decision": result.final_decision
                if hasattr(result, "final_decision")
                else "",
                "consensus_score": result.consensus_score
                if hasattr(result, "consensus_score")
                else 0.85,
            },
        }
    except Exception as e:
        logger.error(f"MultiAgentDebate failed: {e}")
        return {"success": False, "error": str(e)}


async def _run_collective_brainstorming(topic: str, initial: str) -> dict:
    """Запуск CollectiveBrainstorming"""
    try:
        from knowledge_os.app.collective_brainstorming import CollectiveBrainstorming

        brainstorm = CollectiveBrainstorming()
        result = await brainstorm.run_brainstorming(topic, initial)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"CollectiveBrainstorming failed: {e}")
        return {"success": False, "error": str(e)}


async def _run_victoria_synthesis(
    topic: str,
    expert_results: dict[str, Any],
    victoria: VictoriaClient,
    session_id: str,
) -> dict[str, Any]:
    """
    Финальный синтез через Victoria после завершения диалога экспертов.
    """
    final_decision = expert_results.get("final_decision", "")
    consensus_score = expert_results.get("consensus_score", 0.85)

    synthesis_prompt = f"""Ты - синтезатор решений. Проанализируй результаты диалога экспертов и создай финальное обоснованное решение.

Тема: {topic}

Результаты экспертного обсуждения:
{final_decision}

Оценка консенсуса: {consensus_score:.0%}

Твоя задача:
1. Кратко резюмируй ключевые точки консенсуса
2. Выдели спорные моменты (если есть)
3. Предложи финальное решение с обоснованием
4. Оцени уверенность в решении (0-1)

Формат ответа:
## Резюме
<краткое резюме>

## Решение
<финальное решение>

## Уверенность
<оценка 0-1>
"""

    try:
        result = await victoria.run(
            prompt=synthesis_prompt,
            session_id=session_id,
            project_context="atra-web-ide",
        )

        if result.get("status") == "success":
            synthesis_text = result.get("result", "") or result.get("response", "")
            return {
                "success": True,
                "synthesis": synthesis_text,
                "original_decision": final_decision,
                "consensus_score": consensus_score,
            }
        else:
            logger.warning(f"Victoria synthesis failed: {result.get('error')}")
            return {
                "success": False,
                "synthesis": None,
                "original_decision": final_decision,
                "consensus_score": consensus_score,
            }
    except Exception as e:
        logger.error(f"Victoria synthesis error: {e}")
        return {
            "success": False,
            "synthesis": None,
            "original_decision": final_decision,
            "consensus_score": consensus_score,
        }


@router.post("/stream")
async def stream_dialogue(request: DialogueRequest):
    """
    SSE стриминг диалога экспертов в чат.
    Результаты отправляются по мере готовности.
    """
    import asyncio
    import json
    from fastapi.responses import StreamingResponse

    session_id = str(uuid4())

    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'start', 'session_id': session_id, 'topic': request.topic})}\n\n"

            _sessions[session_id] = {
                "status": "in_progress",
                "topic": request.topic,
                "mode": request.mode.value,
                "progress": 0.0,
            }

            if request.mode == DialogueMode.SEQUENTIAL:
                yield f"data: {json.dumps({'type': 'log', 'content': '🎭 Запускаю Совет Экспертов...'})}\n\n"
                result = await _run_expert_council(
                    request.topic, request.initial_proposal or "", request.beautiful_mode
                )
            elif request.mode == DialogueMode.DEBATE:
                yield f"data: {json.dumps({'type': 'log', 'content': '⚔️ Запускаю Мультиагентные Дебаты...'})}\n\n"
                result = await _run_multi_agent_debate(
                    request.topic, request.initial_proposal or "", request.round_limit
                )
            elif request.mode == DialogueMode.COLLABORATION:
                yield f"data: {json.dumps({'type': 'log', 'content': '💡 Запускаю Коллективный Брейншторминг...'})}\n\n"
                result = await _run_collective_brainstorming(
                    request.topic, request.initial_proposal or ""
                )
            else:
                yield f"data: {json.dumps({'type': 'error', 'content': f'Mode {request.mode} not implemented'})}\n\n"
                return

            _sessions[session_id]["progress"] = 0.5

            if result.get("success"):
                r = result["result"]
                final_decision = r.get("final_decision", "")
                consensus_score = r.get("consensus_score", 0.85)

                yield f"data: {json.dumps({'type': 'opinion', 'expert': 'Финальное решение', 'content': final_decision[:500] + '...'})}\n\n"

                _sessions[session_id].update(
                    {
                        "final_decision": final_decision,
                        "consensus_score": consensus_score,
                        "progress": 1.0,
                        "status": "completed",
                    }
                )

                yield f"data: {json.dumps({'type': 'complete', 'session_id': session_id, 'final_decision': final_decision, 'consensus_score': consensus_score})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'content': result.get('error', 'Unknown error')})}\n\n"
                _sessions[session_id]["status"] = "failed"

        except Exception as e:
            logger.error(f"Stream dialogue error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/start", response_model=DialogueResponse)
async def start_dialogue(
    request: DialogueRequest,
    victoria: VictoriaClient = Depends(get_victoria_client),
) -> DialogueResponse:
    """
    Запустить диалог экспертов с опциональным финальным синтезом через Victoria.

    Args:
        request: Параметры диалога
        victoria: VictoriaClient для финального синтеза

    Returns:
        Результат диалога с мнениями экспертов, финальным решением и синтезом от Victoria
    """
    session_id = str(uuid4())

    _sessions[session_id] = {
        "status": "in_progress",
        "topic": request.topic,
        "mode": request.mode.value,
        "progress": 0.0,
    }

    logger.info(f"Starting dialogue session {session_id}: mode={request.mode.value}")

    if request.mode == DialogueMode.SEQUENTIAL:
        result = await _run_expert_council(
            request.topic, request.initial_proposal or "", request.beautiful_mode
        )
    elif request.mode == DialogueMode.DEBATE:
        result = await _run_multi_agent_debate(
            request.topic, request.initial_proposal or "", request.round_limit
        )
    elif request.mode == DialogueMode.COLLABORATION:
        result = await _run_collective_brainstorming(request.topic, request.initial_proposal or "")
    else:
        _sessions[session_id]["status"] = "failed"
        raise HTTPException(status_code=400, detail=f"Mode {request.mode} not implemented")

    _sessions[session_id]["status"] = "completed" if result.get("success") else "failed"
    _sessions[session_id]["progress"] = 1.0

    if result.get("success"):
        r = result["result"]
        final_decision = r.get("final_decision", "")
        consensus_score = r.get("consensus_score", 0.85)

        synthesis_result = await _run_victoria_synthesis(
            topic=request.topic,
            expert_results=r,
            victoria=victoria,
            session_id=session_id,
        )

        victoria_synthesis = synthesis_result.get("synthesis")
        synthesis_by_victoria = synthesis_result.get("success", False)

        _sessions[session_id].update(
            {
                "final_decision": final_decision,
                "consensus_score": consensus_score,
                "victoria_synthesis": victoria_synthesis,
                "synthesis_by_victoria": synthesis_by_victoria,
            }
        )

        return DialogueResponse(
            session_id=session_id,
            topic=request.topic,
            mode=request.mode.value,
            participants=[],  # Заполнить из модулей
            opinions=[],
            final_decision=final_decision,
            consensus_score=consensus_score,
            status="completed",
            victoria_synthesis=victoria_synthesis,
            synthesis_by_victoria=synthesis_by_victoria,
        )
    else:
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))


@router.get("/status/{session_id}", response_model=DialogueStatus)
async def get_status(session_id: str) -> DialogueStatus:
    """Получить статус диалога"""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    s = _sessions[session_id]
    return DialogueStatus(
        session_id=session_id, status=s["status"], progress=s.get("progress", 1.0)
    )


@router.get("/history/{session_id}", response_model=DialogueResponse)
async def get_history(session_id: str) -> DialogueResponse:
    """Получить историю диалога"""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    s = _sessions[session_id]
    return DialogueResponse(
        session_id=session_id,
        topic=s.get("topic", ""),
        mode=s.get("mode", "debate"),
        participants=s.get("participants", []),
        opinions=s.get("opinions", []),
        final_decision=s.get("final_decision", ""),
        consensus_score=s.get("consensus_score"),
        status=s["status"],
        victoria_synthesis=s.get("victoria_synthesis"),
        synthesis_by_victoria=s.get("synthesis_by_victoria", False),
    )


@router.get("/modes")
async def list_modes() -> dict[str, str]:
    """Список доступных режимов"""
    return {
        "sequential": "ExpertCouncil - последовательный мозговой штурм",
        "debate": "MultiAgentDebate - многоканальный спор",
        "collaboration": "CollectiveBrainstorming - 5-фазное проектирование",
        "swarm": "Swarm Intelligence - роение агентов",
    }


class SynthesisRequest(BaseModel):
    session_id: str


class SynthesisResponse(BaseModel):
    session_id: str
    victoria_synthesis: Optional[str] = None
    synthesis_by_victoria: bool = False
    final_decision: str
    consensus_score: Optional[float] = None
    status: str


@router.post("/synthesize/{session_id}", response_model=SynthesisResponse)
async def synthesize_with_victoria(
    session_id: str,
    victoria: VictoriaClient = Depends(get_victoria_client),
) -> SynthesisResponse:
    """
    Перезапустить финальный синтез через Victoria для существующей сессии.
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    s = _sessions[session_id]

    synthesis_result = await _run_victoria_synthesis(
        topic=s.get("topic", ""),
        expert_results={
            "final_decision": s.get("final_decision", ""),
            "consensus_score": s.get("consensus_score", 0.85),
        },
        victoria=victoria,
        session_id=session_id,
    )

    victoria_synthesis = synthesis_result.get("synthesis")
    synthesis_by_victoria = synthesis_result.get("success", False)

    _sessions[session_id].update(
        {
            "victoria_synthesis": victoria_synthesis,
            "synthesis_by_victoria": synthesis_by_victoria,
        }
    )

    return SynthesisResponse(
        session_id=session_id,
        victoria_synthesis=victoria_synthesis,
        synthesis_by_victoria=synthesis_by_victoria,
        final_decision=s.get("final_decision", ""),
        consensus_score=s.get("consensus_score"),
        status=s["status"],
    )
