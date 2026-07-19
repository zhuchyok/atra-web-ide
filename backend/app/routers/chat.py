"""
Chat Router - SSE стриминг для AI чата (Singularity 31.2+ Unified)
Прокси-роутер, передающий все запросы в Victoria Agent.
"""

import asyncio
import json
import logging
import os
import re
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Dict, List, Optional

import httpx
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
from app.services.knowledge_os import KnowledgeOSClient, get_knowledge_os_client
from app.services.ollama import OllamaClient, get_ollama_client
from app.services.victoria import VictoriaClient, get_victoria_client

logger = logging.getLogger(__name__)
router = APIRouter()


_ONE_WORD_DIRECTIVE_RE = re.compile(
    r'^\s*(?:скажи|напиши|ответь)\s+(?:одним?\s+словом|одно\s+слово)\s*[:\-]?\s*[«"“]?([^\n"»”]+?)[»"”]?\s*[.!?]*\s*$',
    re.IGNORECASE,
)
_ONE_WORD_DIRECTIVE_INTENT_RE = re.compile(
    r"^\s*(?:скажи|напиши|ответь)\s+(?:одним?\s+словом|одно\s+слово)\b",
    re.IGNORECASE,
)
_IDENTITY_CHECK_RE = re.compile(
    r"(ты\s+виктория|кто\s+ты|team\s*lead|тимлид|ты\s+atra|виктория\s+team\s+lead)",
    re.IGNORECASE,
)
_EXPERT_DISCUSSION_RE = re.compile(
    r"(консилиум|обсуждени[ея]\s+эксперт|диалог\s+эксперт|мнения?\s+эксперт|эксперты\s+обсудите|собери\s+эксперт)",
    re.IGNORECASE,
)
_BIBLE_KB_RE = re.compile(
    r"(библи[яиюе]|master_reference|changes_from_other_chats|база\s+знани|knowledge\s*base|ag(e)?nts\.md)",
    re.IGNORECASE,
)
_ORG_EXPERTS_RE = re.compile(
    r"(сколько\s+.*эксперт|кто\s+.*эксперт|список\s+эксперт|наша?\s+команд[аы]\s+эксперт)",
    re.IGNORECASE,
)


def _extract_forced_one_word(goal: str) -> Optional[str]:
    """
    Детерминированный ответ для явной команды формата:
    «скажи/ответь/напиши одним словом ...».
    """
    m = _ONE_WORD_DIRECTIVE_RE.match((goal or "").strip())
    if not m:
        return None
    candidate = (m.group(1) or "").strip()
    if not candidate:
        return None
    # Берём первое «слово» без пунктуации, чтобы исключить модельные развёрнутые ответы.
    token_match = re.search(r"[A-Za-zА-Яа-яЁё0-9_+-]+", candidate)
    if token_match:
        return token_match.group(0)
    return None


def _extract_identity_assertion(goal: str) -> Optional[str]:
    """Deterministic persona answer for direct identity checks."""
    g = (goal or "").strip()
    if not g:
        return None
    if _IDENTITY_CHECK_RE.search(g):
        return "Да, я Виктория, Team Lead корпорации ATRA."
    return None


def _is_expert_discussion_request(goal: str) -> bool:
    g = (goal or "").strip()
    if not g:
        return False
    if "[SYSTEM: TEAM_DISCUSSION_MODE]" in g:
        return True
    return bool(_EXPERT_DISCUSSION_RE.search(g))


def _normalize_workspace_paths(goal: str) -> str:
    """Map host workspace paths to container-visible workspace paths."""
    text = (goal or "").strip()
    if not text:
        return text
    host_workspace = os.getenv("ATRA_HOST_WORKSPACE", "/Users/bikos/Documents/atra-web-ide").rstrip(
        "/"
    )
    container_workspace = os.getenv("ATRA_CONTAINER_WORKSPACE", "/workspace/atra-web-ide").rstrip(
        "/"
    )
    if host_workspace and container_workspace and host_workspace in text:
        return text.replace(host_workspace, container_workspace)
    return text


def _looks_like_fs_task(goal: str) -> bool:
    g = (goal or "").lower()
    markers = (
        "/users/",
        "/workspace/",
        "/app/",
        "файл",
        "папк",
        "директори",
        "каталог",
        "list_directory",
        "read_file",
        "прочитай",
        "покажи файлы",
    )
    return any(m in g for m in markers)


def _with_fs_guardrails(goal: str) -> str:
    if not _looks_like_fs_task(goal):
        return goal
    return (
        "КОНТРАКТ ВЫПОЛНЕНИЯ (обязателен):\n"
        "- Для операций с файлами сначала используй реальные инструменты list_directory/read_file.\n"
        "- Не имитируй сканирование и не выдумывай выполненные команды.\n"
        "- Если путь недоступен, верни ACCESS_ERROR с конкретной ошибкой.\n\n"
        f"Задача пользователя:\n{goal}"
    )


def _extract_first_abs_path(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"(/(?:workspace|app|Users)/[^\s,;:!?\"'`()\\]+)", text)
    return m.group(1) if m else None


def _extract_first_int(text: str, default: int, minimum: int = 1, maximum: int = 200) -> int:
    m = re.search(r"\b(\d{1,4})\b", text or "")
    if not m:
        return default
    try:
        v = int(m.group(1))
        return max(minimum, min(maximum, v))
    except Exception:
        return default


def _safe_workspace_path(path_str: str) -> Optional[Path]:
    try:
        p = Path(path_str).resolve()
    except Exception:
        return None
    ws = Path(os.getenv("ATRA_CONTAINER_WORKSPACE", "/workspace/atra-web-ide")).resolve()
    docs = Path("/workspace/global_docs")
    allowed_roots = [ws, docs]
    for root in allowed_roots:
        try:
            p.relative_to(root)
            return p
        except Exception:
            continue
    return None


def _deterministic_fs_fastpath(goal: str) -> Optional[str]:
    """
    Deterministic filesystem fallback for simple requests.
    World-practice pattern: route straightforward IO tasks away from LLM.
    """
    if not _looks_like_fs_task(goal):
        return None
    g = (goal or "").lower()
    norm = _normalize_workspace_paths(goal)
    path_raw = _extract_first_abs_path(norm)
    if not path_raw:
        return None
    path = _safe_workspace_path(path_raw)
    if path is None:
        return "ACCESS_ERROR: Path is outside allowed workspace scope."

    is_read = any(
        k in g for k in ("прочитай", "покажи содержимое файла", "read_file", "первые строки")
    )
    is_list = any(k in g for k in ("покажи", "список", "list_directory", "файлы", "папк"))
    if path.is_file() or (is_read and not path.is_dir()):
        if not path.exists():
            return f"ACCESS_ERROR: File not found: {path}"
        lines_limit = _extract_first_int(g, default=20, minimum=1, maximum=400)
        try:
            content = path.read_text(encoding="utf-8", errors="replace").splitlines()
            head = content[:lines_limit]
            return "\n".join(head) if head else "(file is empty)"
        except Exception as e:
            return f"ACCESS_ERROR: Failed to read file: {e}"

    if path.is_dir() or is_list:
        if not path.exists():
            return f"ACCESS_ERROR: Directory not found: {path}"
        limit = _extract_first_int(g, default=20, minimum=1, maximum=500)
        try:
            items = sorted([p.name for p in path.iterdir()])[:limit]
            return "\n".join(items) if items else "(directory is empty)"
        except Exception as e:
            return f"ACCESS_ERROR: Failed to list directory: {e}"

    return None


def _extract_key_lines(text: str, limit: int = 8) -> List[str]:
    key_lines: List[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            key_lines.append(line.lstrip("#").strip())
        elif line.startswith(("-", "*")):
            key_lines.append(line.lstrip("-* ").strip())
        if len(key_lines) >= limit:
            break
    return [k for k in key_lines if k]


def _extract_embedded_excerpt(goal: str, block_name: str) -> str:
    pattern = (
        rf"\[{re.escape(block_name)}\]\s*(.*?)(?=\n\[[A-Z_ ]+ excerpt\]|\nproject_context=|\Z)"
    )
    m = re.search(pattern, goal or "", flags=re.DOTALL)
    return (m.group(1) or "").strip() if m else ""


def _deterministic_bible_fastpath(goal: str) -> Optional[str]:
    """
    Deterministic answer for requests to study "corporate bible"/knowledge base.
    Avoids clarification loops and guarantees factual result from mounted docs.
    """
    g = (goal or "").strip()
    if not g or not _BIBLE_KB_RE.search(g):
        return None

    doc_specs = [
        ("MASTER_REFERENCE", "/workspace/global_docs/MASTER_REFERENCE.md", 22000),
        ("CHANGES_FROM_OTHER_CHATS", "/workspace/global_docs/CHANGES_FROM_OTHER_CHATS.md", 12000),
        ("AGENTS", "/workspace/atra-web-ide/AGENTS.md", 12000),
    ]
    found: List[tuple[str, str, str]] = []

    # If ask_victoria tool already attached bible excerpts, use them directly.
    embedded_master = _extract_embedded_excerpt(g, "MASTER_REFERENCE excerpt")
    if embedded_master:
        found.append(("MASTER_REFERENCE", "embedded:ask_victoria_context", embedded_master))
    embedded_changes = _extract_embedded_excerpt(g, "CHANGES excerpt")
    if embedded_changes:
        found.append(
            ("CHANGES_FROM_OTHER_CHATS", "embedded:ask_victoria_context", embedded_changes)
        )

    for label, raw_path, max_chars in doc_specs:
        safe = _safe_workspace_path(raw_path)
        if safe is None or not safe.exists() or not safe.is_file():
            continue
        try:
            excerpt = safe.read_text(encoding="utf-8", errors="replace")[:max_chars]
            found.append((label, str(safe), excerpt))
        except Exception:
            continue

    if not found:
        return (
            "ACCESS_ERROR: Не удалось найти файлы корпоративной библии/базы знаний "
            "в разрешённых путях (/workspace/global_docs и /workspace/atra-web-ide)."
        )

    lines: List[str] = ["Да, изучила корпоративную библию и базу знаний. Краткая выжимка:"]
    for label, path, excerpt in found:
        key = _extract_key_lines(excerpt, limit=4)
        lines.append(f"\n[{label}] {path}")
        if key:
            for item in key:
                lines.append(f"- {item}")
        else:
            first_line = next(
                (ln.strip() for ln in excerpt.splitlines() if ln.strip()), "(пустой документ)"
            )
            lines.append(f"- {first_line[:220]}")
    lines.append("\nГотова применять эти правила в следующих ответах и задачах.")
    return "\n".join(lines)


async def _deterministic_org_fastpath(goal: str, knowledge_os: KnowledgeOSClient) -> Optional[str]:
    """
    Fast-path for simple organizational questions about experts.
    Avoids heavy enhanced pipeline and long-task hangs.
    """
    g = (goal or "").strip()
    if not g or not _ORG_EXPERTS_RE.search(g):
        return None
    try:
        experts = await knowledge_os.get_experts()
    except Exception as e:
        logger.debug("org fastpath unavailable: %s", e)
        return None
    if not experts:
        return "Пока не вижу экспертов в базе. Проверьте доступ к Knowledge OS."
    names = [str(e.get("name") or "").strip() for e in experts if str(e.get("name") or "").strip()]
    names = sorted(dict.fromkeys(names))
    preview = ", ".join(names[:20])
    suffix = f" (показаны первые 20 из {len(names)})" if len(names) > 20 else ""
    return f"Сейчас в базе {len(names)} экспертов: {preview}{suffix}."


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
    knowledge_os: KnowledgeOSClient = Depends(get_knowledge_os_client),
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
            domain,
            f"www.{domain}",
        )

    if not dealer:
        # Fallback на дефолтные настройки если домен не найден
        dealer_info = "Компания 'Сетки 21', производство москитных сеток."
    else:
        branding = json.loads(dealer.get("branding") or "{}")
        dealer_info = f"""
        Название: {dealer["name"]}
        Город: {dealer["city"]}
        Телефон: {dealer["phone"]}
        Email: {dealer["email"]}
        Адрес: {dealer["address"]}
        Режим работы: {branding.get("working_hours", "не указан")}
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
    - Если не знаешь ответа, предложи связаться по телефону {dealer["phone"] if dealer else "указанному на сайте"}.
    """

    # 4. Вызов Ollama
    try:
        response = await ollama.generate(
            prompt=request.message, model="qwen2.5:0.5b", system=system_prompt
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
    """Запрос для инструмента ask_victoria (Singularity 31.2+)"""

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
    """SSE стриминг ответа (Singularity 31.2+ Unified) — прокси к Victoria /stream"""
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
    knowledge_os: KnowledgeOSClient = Depends(get_knowledge_os_client),
    format: Optional[str] = Query(None, description="Response format: json for JSON body"),
):
    """
    Singularity 31.2+: единая точка делегирования в Victoria.
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

    forced_one_word = _extract_forced_one_word(goal_stripped)
    if forced_one_word:
        ASK_VICTORIA_TOTAL.labels(status="success").inc()
        if format == "json":
            return JSONResponse(content={"status": "success", "result": forced_one_word})
        return PlainTextResponse(forced_one_word)
    identity_assertion = _extract_identity_assertion(goal_stripped)
    if identity_assertion:
        ASK_VICTORIA_TOTAL.labels(status="success").inc()
        if format == "json":
            return JSONResponse(content={"status": "success", "result": identity_assertion})
        return PlainTextResponse(identity_assertion)
    if _ONE_WORD_DIRECTIVE_INTENT_RE.match(goal_stripped):
        msg = "После команды 'одно слово' укажите само слово."
        if format == "json":
            return JSONResponse(status_code=422, content={"status": "error", "result": msg})
        return PlainTextResponse(msg, status_code=422)

    bible_fast_result = _deterministic_bible_fastpath(goal_stripped)
    if bible_fast_result is not None:
        ASK_VICTORIA_TOTAL.labels(status="success").inc()
        if format == "json":
            return JSONResponse(content={"status": "success", "result": bible_fast_result})
        return PlainTextResponse(bible_fast_result)

    fs_fast_result = _deterministic_fs_fastpath(goal_stripped)
    if fs_fast_result is not None:
        ASK_VICTORIA_TOTAL.labels(status="success").inc()
        if format == "json":
            return JSONResponse(content={"status": "success", "result": fs_fast_result})
        return PlainTextResponse(fs_fast_result)

    org_fast_result = await _deterministic_org_fastpath(goal_stripped, knowledge_os)
    if org_fast_result is not None:
        ASK_VICTORIA_TOTAL.labels(status="success").inc()
        if format == "json":
            return JSONResponse(content={"status": "success", "result": org_fast_result})
        return PlainTextResponse(org_fast_result)

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

    goal_normalized = _normalize_workspace_paths(goal_stripped)
    goal_for_victoria = _with_fs_guardrails(goal_normalized)
    if _is_expert_discussion_request(goal_stripped):
        goal_for_victoria = f"[SYSTEM: TEAM_DISCUSSION_MODE]\n{goal_for_victoria}"
    max_wait_sec = float(os.getenv("ASK_VICTORIA_MAX_WAIT_SEC", "15"))

    try:
        # Prefer async + polling client path: gives Victoria more room for deep execution
        # and reduces early fallback to quick sync-safe responses.
        result = await victoria.run(
            prompt=goal_for_victoria,
            project_context=(body.project_context or "atra-web-ide").strip(),
            session_id=session_id,
            chat_history=body.chat_history,
            use_enhanced=True,
            max_poll_wait_sec=max_wait_sec,
        )
        if (result.get("status") or "").lower() == "processing":
            ASK_VICTORIA_TOTAL.labels(status="processing").inc()
            task_id = result.get("task_id") or ""
            status_url = f"/api/chat/ask-victoria/status/{task_id}" if task_id else ""
            msg = (
                "Victoria выполняет длинную задачу. Продолжаю ждать через status polling."
                if task_id
                else "Victoria выполняет длинную задачу, попробуйте повторить запрос чуть позже."
            )
            if format == "json":
                return JSONResponse(
                    status_code=202,
                    content={
                        "status": "processing",
                        "result": msg,
                        "task_id": task_id,
                        "status_url": status_url,
                        "poll_after_sec": 3,
                    },
                    headers={"Retry-After": "3"},
                )
            return PlainTextResponse(msg, status_code=202, headers={"Retry-After": "3"})
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
        from app.utils.victoria_response_guard import is_victoria_stub

        if is_victoria_stub(content, status=str(result.get("status") or "")):
            ASK_VICTORIA_TOTAL.labels(status="error").inc()
            msg = (
                "Rejected Victoria stub/queue/rule-fallback response. "
                "Retry the request; do not invent an answer from this stub."
            )
            if format == "json":
                return JSONResponse(status_code=503, content={"status": "error", "result": msg})
            return PlainTextResponse(msg, status_code=503)
        clarification = result.get("clarification_questions")
        if clarification:
            bible_fallback = _deterministic_bible_fastpath(goal_stripped)
            if bible_fallback is not None:
                ASK_VICTORIA_TOTAL.labels(status="success").inc()
                if format == "json":
                    return JSONResponse(content={"status": "success", "result": bible_fallback})
                return PlainTextResponse(bible_fallback)
            # Deterministic fallback: avoid pointless clarification loops for simple fs tasks.
            fs_fallback = _deterministic_fs_fastpath(goal_stripped)
            if fs_fallback is not None:
                ASK_VICTORIA_TOTAL.labels(status="success").inc()
                if format == "json":
                    return JSONResponse(content={"status": "success", "result": fs_fallback})
                return PlainTextResponse(fs_fallback)
            if isinstance(clarification, list):
                lines = [
                    f"Мне нужно уточнить: {q}" if isinstance(q, str) else str(q)
                    for q in clarification
                ]
                content = "\n".join(lines) + ("\n\n" + content if content else "")
            else:
                content = str(clarification) + ("\n\n" + content if content else "")
        elif _BIBLE_KB_RE.search(goal_stripped) and "нужно уточнение" in content.lower():
            bible_fallback = _deterministic_bible_fastpath(goal_stripped)
            if bible_fallback is not None:
                ASK_VICTORIA_TOTAL.labels(status="success").inc()
                if format == "json":
                    return JSONResponse(content={"status": "success", "result": bible_fallback})
                return PlainTextResponse(bible_fallback)
        ASK_VICTORIA_TOTAL.labels(status="success").inc()
        if format == "json":
            return JSONResponse(content={"status": "success", "result": content})
        return PlainTextResponse(content)
    except asyncio.TimeoutError:
        ASK_VICTORIA_TOTAL.labels(status="error").inc()
        msg = "Victoria не успела ответить (таймаут backend). Попробуйте через минуту или сократите запрос."
        if format == "json":
            return JSONResponse(status_code=503, content={"status": "error", "result": msg})
        return PlainTextResponse(msg, status_code=503)
    except Exception as e:
        logger.warning("ask_victoria error: %s", e)
        ASK_VICTORIA_TOTAL.labels(status="error").inc()
        msg = _user_facing_error(str(e))
        if format == "json":
            return JSONResponse(status_code=503, content={"status": "error", "result": msg})
        return PlainTextResponse(msg, status_code=503)
    finally:
        release_victoria_slot()


@router.get("/ask-victoria/status/{task_id}")
async def ask_victoria_status(
    task_id: str,
    victoria: VictoriaClient = Depends(get_victoria_client),
    format: Optional[str] = Query(None, description="Response format: json for JSON body"),
):
    """Proxy Victoria long-task status for Open WebUI tool polling."""
    if not (task_id or "").strip():
        if format == "json":
            return JSONResponse(
                status_code=422, content={"status": "error", "result": "task_id required"}
            )
        return PlainTextResponse("task_id required", status_code=422)
    try:
        status_url = f"{victoria.base_url}/run/status/{task_id.strip()}"
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            r = await client.get(status_url)
            if r.status_code == 404:
                payload = {
                    "status": "error",
                    "result": "Task not found (possibly expired/restarted).",
                }
            else:
                r.raise_for_status()
                st = r.json()
                s = (st.get("status") or "").lower()
                if s == "completed":
                    out = st.get("output") or st.get("result") or ""
                    from app.utils.victoria_response_guard import is_victoria_stub

                    if is_victoria_stub(str(out), status="completed"):
                        payload = {
                            "status": "error",
                            "result": (
                                "Rejected Victoria stub/queue/rule-fallback response. "
                                "Retry; do not treat this as success."
                            ),
                        }
                    else:
                        payload = {"status": "success", "result": out}
                elif s == "failed":
                    payload = {"status": "error", "result": st.get("error") or "Task failed."}
                else:
                    payload = {
                        "status": "processing",
                        "result": "Task is still running.",
                        "poll_after_sec": 3,
                    }
        if format == "json":
            if payload.get("status") == "processing":
                return JSONResponse(status_code=202, content=payload, headers={"Retry-After": "3"})
            return JSONResponse(content=payload)
        if payload.get("status") == "processing":
            return PlainTextResponse(
                payload.get("result", ""), status_code=202, headers={"Retry-After": "3"}
            )
        return PlainTextResponse(payload.get("result", ""))
    except Exception as e:
        logger.warning("ask_victoria_status error: %s", e)
        if format == "json":
            return JSONResponse(
                status_code=503, content={"status": "error", "result": "Status check failed"}
            )
        return PlainTextResponse("Status check failed", status_code=503)


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
