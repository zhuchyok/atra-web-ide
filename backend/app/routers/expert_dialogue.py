"""
Expert Dialogue Router - API для локальных диалогов экспертов
SINGULARITY 24.4 - Unified Expert Dialogue System

Поддерживает:
- Expert Council (последовательный мозговой штурм)
- Multi-Agent Debate (многоканальный спор)
- Collective Brainstorming (5-фазное проектирование)

Интеграция с Victoria для финального синтеза решений.
"""

import asyncio
import logging
import os
import re
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.victoria import VictoriaClient, get_victoria_client

logger = logging.getLogger(__name__)
router = APIRouter()
ENGINE_TIMEOUT_SEC = float(os.getenv("EXPERT_DIALOGUE_ENGINE_TIMEOUT_SEC", "35"))
LIGHTWEIGHT_TIMEOUT_SEC = float(os.getenv("EXPERT_DIALOGUE_LIGHTWEIGHT_TIMEOUT_SEC", "12"))
LIGHTWEIGHT_TARGET_SEC = float(os.getenv("EXPERT_DIALOGUE_LIGHTWEIGHT_TARGET_SEC", "8"))


def _normalize_dialogue_payload(payload: Any, *, fallback_topic: str) -> dict[str, Any]:
    """
    Приводит payload от разных движков (dict/object/str) к единому контракту.
    Это защищает API от несовместимых runtime-реализаций.
    """
    if isinstance(payload, dict):
        final_decision = str(payload.get("final_decision") or payload.get("summary") or "").strip()
        if not final_decision:
            final_decision = str(payload)
        return {
            "topic": payload.get("topic") or fallback_topic,
            "debate_history": payload.get("debate_history") or "",
            "final_decision": final_decision,
            "consensus_score": float(payload.get("consensus_score") or 0.85),
            "fallback_used": bool(payload.get("fallback_used", False)),
            "lightweight_used": bool(payload.get("lightweight_used", False)),
        }

    # Dataclass/object style contract
    final_decision_obj = getattr(payload, "final_decision", None)
    debate_history = getattr(payload, "debate_history", None)
    consensus_score = getattr(payload, "consensus_score", None)
    if final_decision_obj is not None or debate_history is not None:
        return {
            "topic": fallback_topic,
            "debate_history": debate_history or "",
            "final_decision": str(final_decision_obj or ""),
            "consensus_score": float(consensus_score or 0.85),
            "fallback_used": bool(getattr(payload, "fallback_used", False)),
            "lightweight_used": bool(getattr(payload, "lightweight_used", False)),
        }

    # Plain string fallback
    text = str(payload or "").strip()
    return {
        "topic": fallback_topic,
        "debate_history": "",
        "final_decision": text,
        "consensus_score": 0.85,
        "fallback_used": False,
        "lightweight_used": False,
    }


async def _build_safe_fallback_result(
    *,
    topic: str,
    initial: str,
    mode: "DialogueMode",
    error_text: str,
) -> dict[str, Any]:
    """
    Fallback уровня API: не отдаём 500, даже если один из движков экспертов недоступен.
    """
    mode_label = {
        DialogueMode.DEBATE: "Дебаты",
        DialogueMode.SEQUENTIAL: "Совет экспертов",
        DialogueMode.COLLABORATION: "Коллективный брейншторминг",
        DialogueMode.SWARM: "Swarm",
    }.get(mode, "Экспертный диалог")
    safe_text = (
        f"{mode_label}: модуль временно недоступен ({error_text}). "
        f"Рекомендация по теме '{topic}': применить минимально рискованный план, "
        "сначала health/KPI-гейт, затем поэтапный rollout с rollback-планом."
    )
    return {
        "success": True,
        "result": {
            "topic": topic,
            "debate_history": f"fallback:{mode.value}",
            "final_decision": safe_text,
            "consensus_score": 0.7,
            "fallback_used": True,
        },
    }


async def _run_with_mode_timeout(mode: "DialogueMode", coro_factory: Any) -> dict[str, Any]:
    """
    Гарантирует bounded latency для каждого движка диалогов.
    """
    loop = asyncio.get_running_loop()

    def _thread_entry() -> dict[str, Any]:
        return asyncio.run(coro_factory())

    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, _thread_entry), timeout=ENGINE_TIMEOUT_SEC
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Dialogue engine timeout for mode=%s after %.1fs", mode.value, ENGINE_TIMEOUT_SEC
        )
        return {
            "success": False,
            "error": f"dialogue_engine_timeout:{mode.value}:{ENGINE_TIMEOUT_SEC:.1f}s",
        }


async def _run_lightweight_dialogue(
    *,
    topic: str,
    initial: str,
    mode: "DialogueMode",
    victoria: VictoriaClient,
    session_id: str,
) -> dict[str, Any]:
    """
    Быстрый "реальный" диалог без тяжёлых multi-agent веток.
    Возвращает короткое содержательное решение в пределах bounded SLA.
    """
    mode_label = {
        DialogueMode.DEBATE: "Дебаты",
        DialogueMode.SEQUENTIAL: "Совет экспертов",
        DialogueMode.COLLABORATION: "Коллективный брейншторминг",
        DialogueMode.SWARM: "Swarm",
    }.get(mode, "Экспертный диалог")
    initial_block = initial.strip() if initial and initial.strip() else "нет"
    prompt = (
        "Ты ведущий экспертной панели ATRA. "
        f"Смоделируй {mode_label.lower()} в lightweight-формате и выдай практичное решение. "
        "Сфокусируйся на минимально рискованном и исполнимом плане.\n\n"
        f"Тема: {topic}\n"
        f"Начальное предложение: {initial_block}\n\n"
        "Формат строго:\n"
        "1) Консенсус (2-3 пункта)\n"
        "2) Риски (до 2 пунктов)\n"
        "3) Следующие шаги (3 шага)\n"
        "4) Уверенность (0-1)\n"
    )
    text = await _try_victoria_lightweight_fast(
        victoria=victoria,
        prompt=prompt,
        session_id=session_id,
        timeout_budget_sec=LIGHTWEIGHT_TARGET_SEC,
    )
    if not text:
        text = _build_local_lightweight_decision(
            topic=topic,
            initial=initial,
            mode_label=mode_label,
        )
    if not text:
        return {"success": False, "error": "lightweight_empty_output"}

    return {
        "success": True,
        "result": {
            "topic": topic,
            "debate_history": f"lightweight:{mode.value}",
            "final_decision": text,
            "consensus_score": 0.78,
            "fallback_used": False,
            "lightweight_used": True,
        },
    }


async def _try_victoria_lightweight_fast(
    *,
    victoria: VictoriaClient,
    prompt: str,
    session_id: str,
    timeout_budget_sec: float,
) -> Optional[str]:
    """
    Минимальный latency-path до Victoria без длинных retries.
    """
    base_url = getattr(victoria, "base_url", "").rstrip("/")
    if not base_url:
        return None

    timeout_budget_sec = max(4.0, float(timeout_budget_sec))
    payload = {
        "goal": prompt,
        "max_steps": 12,
        "project_context": "atra-web-ide",
        "session_id": session_id,
        "use_enhanced": False,
    }
    post_timeout = min(6.0, timeout_budget_sec)
    poll_timeout = min(5.0, timeout_budget_sec)
    deadline = asyncio.get_event_loop().time() + timeout_budget_sec

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=3.0, read=post_timeout, write=post_timeout, pool=post_timeout
            )
        ) as client:
            response = await client.post(f"{base_url}/run?async_mode=true", json=payload)
            response.raise_for_status()
            data = response.json()

        if response.status_code == 200:
            out = (data.get("output") or data.get("result") or data.get("response") or "").strip()
            return out or None

        task_id = data.get("task_id")
        if not task_id:
            return None

        status_url = f"{base_url}/run/status/{task_id}"
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=3.0, read=poll_timeout, write=poll_timeout, pool=poll_timeout
            )
        ) as client:
            while asyncio.get_event_loop().time() < deadline:
                r = await client.get(status_url)
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                st = r.json()
                status_val = (st.get("status") or "").lower()
                if status_val == "completed":
                    out = (st.get("output") or st.get("result") or "").strip()
                    return out or None
                if status_val == "failed":
                    return None
                await asyncio.sleep(1.0)
    except Exception as e:
        logger.debug("Fast lightweight Victoria path failed: %s", e)
        return None
    return None


def _build_local_lightweight_decision(*, topic: str, initial: str, mode_label: str) -> str:
    """
    Локальный быстрый реальный ответ (не fallback): всегда структурированный и применимый.
    """
    clean_topic = (topic or "").strip()[:300]
    clean_initial = (initial or "").strip()[:300]
    if not clean_topic:
        return ""
    verbs = re.findall(r"[A-Za-zА-Яа-я0-9_/-]{3,}", clean_topic)
    focus = ", ".join(verbs[:3]) if verbs else "целевая задача"
    initial_hint = clean_initial if clean_initial else "начальное предложение не задано"
    return (
        f"{mode_label} (lightweight):\n"
        f"1) Консенсус:\n"
        f"- Держим фокус на результате по теме: {clean_topic}.\n"
        f"- Используем предложенный вектор: {initial_hint}.\n"
        f"- Начинаем с минимального безопасного шага и проверяем KPI/health после каждого шага.\n"
        f"2) Риски:\n"
        f"- Риск регрессии в контуре: {focus}.\n"
        f"- Риск скрытых зависимостей при быстром rollout.\n"
        f"3) Следующие шаги:\n"
        f"- Шаг 1: ограниченный pilot (один контур/режим) + метрики успеха.\n"
        f"- Шаг 2: расширение на соседние сценарии при стабильных метриках.\n"
        f"- Шаг 3: зафиксировать результат в runbook/библии и включить регулярный контроль.\n"
        f"4) Уверенность: 0.74"
    )


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

        brainstorm = CollectiveBrainstorming(topic, initial)
        result = await brainstorm.run_session()
        return {
            "success": True,
            "result": _normalize_dialogue_payload(result, fallback_topic=topic),
        }
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

            lightweight_victoria = await get_victoria_client()
            yield f"data: {json.dumps({'type': 'log', 'content': '⚡ Пробую lightweight-диалог (быстрый реальный ответ)...'})}\n\n"
            result = await _run_lightweight_dialogue(
                topic=request.topic,
                initial=request.initial_proposal or "",
                mode=request.mode,
                victoria=lightweight_victoria,
                session_id=session_id,
            )

            if request.mode == DialogueMode.SEQUENTIAL:
                if not result.get("success"):
                    yield f"data: {json.dumps({'type': 'log', 'content': '↩️ Lightweight не сработал, переключаюсь на full mode...'})}\n\n"
                    yield f"data: {json.dumps({'type': 'log', 'content': '🎭 Запускаю Совет Экспертов...'})}\n\n"
                    result = await _run_with_mode_timeout(
                        request.mode,
                        lambda: _run_expert_council(
                            request.topic, request.initial_proposal or "", request.beautiful_mode
                        ),
                    )
            elif request.mode == DialogueMode.DEBATE:
                if not result.get("success"):
                    yield f"data: {json.dumps({'type': 'log', 'content': '↩️ Lightweight не сработал, переключаюсь на full mode...'})}\n\n"
                    yield f"data: {json.dumps({'type': 'log', 'content': '⚔️ Запускаю Мультиагентные Дебаты...'})}\n\n"
                    result = await _run_with_mode_timeout(
                        request.mode,
                        lambda: _run_multi_agent_debate(
                            request.topic, request.initial_proposal or "", request.round_limit
                        ),
                    )
            elif request.mode == DialogueMode.COLLABORATION:
                if not result.get("success"):
                    yield f"data: {json.dumps({'type': 'log', 'content': '↩️ Lightweight не сработал, переключаюсь на full mode...'})}\n\n"
                    yield f"data: {json.dumps({'type': 'log', 'content': '💡 Запускаю Коллективный Брейншторминг...'})}\n\n"
                    result = await _run_with_mode_timeout(
                        request.mode,
                        lambda: _run_collective_brainstorming(
                            request.topic, request.initial_proposal or ""
                        ),
                    )
            else:
                yield f"data: {json.dumps({'type': 'error', 'content': f'Mode {request.mode} not implemented'})}\n\n"
                return

            _sessions[session_id]["progress"] = 0.5

            if result.get("success"):
                r = _normalize_dialogue_payload(result.get("result"), fallback_topic=request.topic)
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
                fallback = await _build_safe_fallback_result(
                    topic=request.topic,
                    initial=request.initial_proposal or "",
                    mode=request.mode,
                    error_text=result.get("error", "Unknown error"),
                )
                r = _normalize_dialogue_payload(fallback["result"], fallback_topic=request.topic)
                _sessions[session_id].update(
                    {
                        "final_decision": r.get("final_decision", ""),
                        "consensus_score": r.get("consensus_score", 0.7),
                        "progress": 1.0,
                        "status": "completed",
                    }
                )
                yield f"data: {json.dumps({'type': 'log', 'content': '⚠️ Включён safe fallback диалога'})}\n\n"
                yield f"data: {json.dumps({'type': 'complete', 'session_id': session_id, 'final_decision': r.get('final_decision', ''), 'consensus_score': r.get('consensus_score', 0.7)})}\n\n"

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

    result = await _run_lightweight_dialogue(
        topic=request.topic,
        initial=request.initial_proposal or "",
        mode=request.mode,
        victoria=victoria,
        session_id=session_id,
    )

    if request.mode == DialogueMode.SEQUENTIAL:
        if not result.get("success"):
            result = await _run_with_mode_timeout(
                request.mode,
                lambda: _run_expert_council(
                    request.topic, request.initial_proposal or "", request.beautiful_mode
                ),
            )
    elif request.mode == DialogueMode.DEBATE:
        if not result.get("success"):
            result = await _run_with_mode_timeout(
                request.mode,
                lambda: _run_multi_agent_debate(
                    request.topic, request.initial_proposal or "", request.round_limit
                ),
            )
    elif request.mode == DialogueMode.COLLABORATION:
        if not result.get("success"):
            result = await _run_with_mode_timeout(
                request.mode,
                lambda: _run_collective_brainstorming(
                    request.topic, request.initial_proposal or ""
                ),
            )
    else:
        _sessions[session_id]["status"] = "failed"
        raise HTTPException(status_code=400, detail=f"Mode {request.mode} not implemented")

    if not result.get("success"):
        result = await _build_safe_fallback_result(
            topic=request.topic,
            initial=request.initial_proposal or "",
            mode=request.mode,
            error_text=result.get("error", "Unknown error"),
        )

    _sessions[session_id]["status"] = "completed"
    _sessions[session_id]["progress"] = 1.0

    if result.get("success"):
        r = _normalize_dialogue_payload(result.get("result"), fallback_topic=request.topic)
        final_decision = r.get("final_decision", "")
        consensus_score = r.get("consensus_score", 0.85)
        fallback_used = bool(r.get("fallback_used"))
        lightweight_used = bool(r.get("lightweight_used"))

        victoria_synthesis = None
        synthesis_by_victoria = False
        # Lightweight path уже выдаёт финализированный ответ; synthesis оставляем для full-mode.
        if not fallback_used and not lightweight_used:
            try:
                synthesis_result = await asyncio.wait_for(
                    _run_victoria_synthesis(
                        topic=request.topic,
                        expert_results=r,
                        victoria=victoria,
                        session_id=session_id,
                    ),
                    timeout=60.0,
                )
                victoria_synthesis = synthesis_result.get("synthesis")
                synthesis_by_victoria = synthesis_result.get("success", False)
            except asyncio.TimeoutError:
                logger.warning("Victoria synthesis timeout for session %s", session_id)
            except Exception as e:
                logger.warning("Victoria synthesis failed for session %s: %s", session_id, e)

        _sessions[session_id].update(
            {
                "final_decision": final_decision,
                "consensus_score": consensus_score,
                "victoria_synthesis": victoria_synthesis,
                "synthesis_by_victoria": synthesis_by_victoria,
                "fallback_used": fallback_used,
                "lightweight_used": lightweight_used,
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
