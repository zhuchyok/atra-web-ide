import asyncio
import json
import os
import re
import subprocess
import uuid
from datetime import datetime
from typing import Any, Optional

import asyncpg

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")

# Connection pool для PostgreSQL (решает проблему "too many clients already")
_db_pool: Optional[asyncpg.Pool] = None

# MLX Request Queue для приоритетной обработки Совета
try:
    from mlx_request_queue import RequestPriority, get_request_queue

    _mlx_queue = get_request_queue()
except ImportError:
    _mlx_queue = None
    RequestPriority = None


async def get_db_pool() -> asyncpg.Pool:
    """Получить или создать connection pool для PostgreSQL"""
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(
            DB_URL,
            min_size=2,
            max_size=10,
            command_timeout=60,
            max_inactive_connection_lifetime=300,
        )
    return _db_pool


async def close_db_pool():
    """Закрыть connection pool"""
    global _db_pool
    if _db_pool is not None:
        await _db_pool.close()
        _db_pool = None


def is_stub_directive(text: Optional[str]) -> bool:
    """True if Victoria returned a queue ack instead of a real board directive."""
    t = (text or "").strip()
    if not t or len(t) < 40:
        return True
    try:
        from victoria_response_guard import is_victoria_stub
    except ImportError:
        try:
            from knowledge_os.app.victoria_response_guard import is_victoria_stub
        except ImportError:
            return "queued to postgresql" in t.lower()
    return is_victoria_stub(t)


_PLACEHOLDER_DECISION_RE = re.compile(
    r"\[(?:одна фраза|2-3[^]]*|кратко|0\.0-1\.0|одно предложение|N пункт[^\]]*)\]"
    r"|решение:\s*\["
    r"|пример\s+\d+\s+из",
    re.IGNORECASE,
)


def is_low_quality_directive(text: Optional[str]) -> bool:
    """
    True if text is prompt-echo, instructional placeholder, or empty decision.
    Used to reject smollm-style copies of the compact template.
    """
    t = (text or "").strip()
    if not t or len(t) < 40:
        return True
    if is_stub_directive(t):
        return True
    low = t.lower()
    if _PLACEHOLDER_DECISION_RE.search(t):
        return True
    echo_markers = (
        "вопрос от пользователя",
        "вы - совет директоров",
        "вы — совет директоров",
        "задача: примите стратегическое",
        "формат: строгий корпоративный",
        "ответь только в формате",
    )
    if any(m in low for m in echo_markers):
        return True
    decision_match = re.search(r"(?:решение|decision):\s*(.+)", t, re.IGNORECASE)
    if not decision_match:
        # Long dump without РЕШЕНИЕ is usually a prompt restatement.
        return len(t) > 350
    decision = decision_match.group(1).strip()
    if len(decision) < 12:
        return True
    if decision.startswith("[") or "одна фраза" in decision.lower():
        return True
    return False


def _summarize_context(raw: str, *, limit: int = 400) -> str:
    """Compact context for the board prompt — avoid dumping raw KB (CODE-queue trap)."""
    text = re.sub(r"\s+", " ", (raw or "").strip())
    if not text:
        return "нет данных"
    # Neutralize common CODE-queue triggers inside embedded context.
    text = re.sub(r"\bcode\b", "software", text, flags=re.IGNORECASE)
    text = text.replace("код", "ПО")
    return text[:limit]


def _resolve_board_reports_dir() -> str:
    """
    Writable directory for Markdown board directives.
    Prefer BOARD_REPORTS_DIR (RW docker volume). Never rely on /app when mounted :ro.
    """
    candidates = []
    env_dir = (os.getenv("BOARD_REPORTS_DIR") or "").strip()
    if env_dir:
        candidates.append(env_dir)
    if os.path.exists("/.dockerenv"):
        candidates.extend(["/data/board_reports", "/tmp/board_reports"])
    else:
        candidates.append("docs/board_reports")
    candidates.append("/tmp/board_reports")

    for cand in candidates:
        try:
            os.makedirs(cand, exist_ok=True)
            probe = os.path.join(cand, ".write_probe")
            with open(probe, "w", encoding="utf-8") as _p:
                _p.write("ok")
            os.remove(probe)
            return cand
        except OSError:
            continue
    raise OSError("no writable board_reports directory")


def _publish_board_markdown(
    *,
    directive: str,
    okr_context: str = "",
    tasks_context: str = "",
    title: str = "СТРАТЕГИЧЕСКАЯ ДИРЕКТИВА СОВЕТА ДИРЕКТОРОВ",
) -> Optional[str]:
    """Write board directive Markdown + LATEST.md. Returns filepath or None."""
    try:
        reports_dir = _resolve_board_reports_dir()
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filepath = os.path.join(reports_dir, f"board_directive_{date_str}.md")
        md_content = f"""# 🏛 {title}
**Дата:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} MSK
**Статус:** ДЕЙСТВУЕТ (24 часа)

## 📊 КОНТЕКСТ ЗАСЕДАНИЯ
### Текущие цели (OKR)
{okr_context if okr_context else "Цели не заданы."}

### Операционный статус
{tasks_context if tasks_context else "Нет данных по задачам."}

---

## 📜 ТЕКСТ ДИРЕКТИВЫ
{directive}

---
*Документ сформирован автоматически ИИ-корпорацией Singularity 10.0. Все решения подлежат исполнению экспертами Atra Core.*
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)
        with open(os.path.join(reports_dir, "LATEST.md"), "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"📄 Директива опубликована: {filepath}")
        return filepath
    except Exception as e:
        print(f"⚠️ Не удалось опубликовать Markdown отчет: {e}")
        return None


async def _poll_victoria_task(
    client: Any, base: str, task_id: str, *, timeout_sec: float = 300.0
) -> str:
    """Poll GET /run/status/{task_id} until completed or timeout."""
    import time

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            resp = await client.get(f"{base}/run/status/{task_id}")
            if resp.status_code != 200:
                await asyncio.sleep(3)
                continue
            data = resp.json()
            status = str(data.get("status") or "").lower()
            output = data.get("output") or data.get("result") or data.get("response") or ""
            output = str(output).strip()
            if (
                status in ("completed", "success", "done")
                and output
                and not is_stub_directive(output)
            ):
                return output
            if status in ("failed", "cancelled", "error"):
                return ""
        except Exception as e:
            print(f"⚠️ Board poll status failed: {e}")
        await asyncio.sleep(4)
    return ""


async def _call_victoria_board_directive(
    *,
    okr_summary: str,
    tasks_summary: str,
    insights_summary: str,
) -> Optional[str]:
    """
    Sync Victoria /run for board meeting.
    Avoids CODE-queue hijack; rejects/polls queue stubs; falls back to local LLM.
    """
    import httpx

    victoria_base = (os.getenv("VICTORIA_URL") or "http://victoria-agent:8000").rstrip("/")
    # Keep goal free of raw KB dumps and avoid embedding the substring "code"/"код".
    goal = f"""Проведи заседание Совета Директоров (strategic board meeting).

Краткий операционный срез (без сырых файлов):
- OKR: {okr_summary}
- Задачи: {tasks_summary}
- Новые знания (сводка): {insights_summary}

Сформулируй ДИРЕКТИВУ СОВЕТА строго в формате (без квадратных скобок и плейсхолдеров):
РЕШЕНИЕ: главное направление на 24 часа одной фразой
ОБОСНОВАНИЕ: почему это важно (2-3 предложения)
РИСКИ: список конкретных рисков
УВЕРЕННОСТЬ: число от 0.0 до 1.0
ФОКУСЫ:
1) первый фокус
2) второй фокус
3) третий фокус
"""
    timeout = float(os.getenv("BOARD_VICTORIA_TIMEOUT_SEC", "480"))
    board_model = os.getenv("BOARD_CONSULT_MODEL", "phi3.5:3.8b")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{victoria_base}/run",
                params={"async_mode": "false"},
                json={
                    "goal": goal,
                    "project_context": "atra-web-ide",
                },
            )
            if resp.status_code not in (200, 202):
                print(f"⚠️ Board Victoria HTTP {resp.status_code}: {resp.text[:200]}")
            else:
                data = resp.json()
                directive = str(
                    data.get("output") or data.get("result") or data.get("response") or ""
                ).strip()
                if is_stub_directive(directive) or is_low_quality_directive(directive):
                    # Extract task id and poll if Victoria queued despite sync request.
                    m = re.search(
                        r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
                        directive,
                        re.I,
                    )
                    if m and is_stub_directive(directive):
                        print(f"⚠️ Board got queue stub, polling task {m.group(1)}...")
                        polled = await _poll_victoria_task(
                            client, victoria_base, m.group(1), timeout_sec=min(300.0, timeout)
                        )
                        if polled and not is_low_quality_directive(polled):
                            return polled
                    print("⚠️ Board Victoria returned stub/low-quality; trying local fallback")
                elif directive:
                    return directive
    except Exception as e:
        print(f"⚠️ Board Victoria call failed: {e}")

    # Local fallback — still a real directive, not a queue ack.
    try:
        try:
            from dialogue_llm import generate_dialogue, is_incomplete_text
        except ImportError:
            from knowledge_os.app.dialogue_llm import generate_dialogue, is_incomplete_text

        gen = await generate_dialogue(goal, expert_name="Виктория", model_hint=board_model)
        if (
            gen.ok
            and gen.text
            and not is_incomplete_text(gen.text)
            and not is_low_quality_directive(gen.text)
        ):
            print("✅ Board directive via dialogue_llm fallback")
            return gen.text.strip()
    except Exception as e:
        print(f"⚠️ Board dialogue_llm fallback failed: {e}")

    try:
        from ai_core import run_smart_agent_async

        text = await asyncio.wait_for(
            run_smart_agent_async(goal, expert_name="Виктория", category="reasoning", is_vip=True),
            timeout=float(os.getenv("BOARD_LOCAL_FALLBACK_TIMEOUT_SEC", "180")),
        )
        text = str(text or "").strip()
        if text and not is_low_quality_directive(text):
            print("✅ Board directive via ai_core fallback")
            return text
    except Exception as e:
        print(f"⚠️ Board ai_core fallback failed: {e}")

    return None


def parse_directive_structure(directive_text: str) -> dict[str, Any]:
    """
    Парсинг текста директивы в структурированный формат.
    Извлекает: decision, rationale, risks, confidence, recommend_human_review
    """
    structured = {
        "decision": "",
        "rationale": "",
        "risks": [],
        "confidence": 0.8,
        "action_items": [],
    }

    # Попытка извлечь decision (первая строка после "РЕШЕНИЕ:" или просто первое предложение)
    decision_match = re.search(
        r"(?:РЕШЕНИЕ|DECISION):\s*(.+?)(?:\n|$)", directive_text, re.IGNORECASE
    )
    if decision_match:
        structured["decision"] = decision_match.group(1).strip()
    else:
        # Берем первое предложение как decision
        first_sentence = (
            directive_text.split(".")[0] if "." in directive_text else directive_text[:200]
        )
        structured["decision"] = first_sentence.strip()

    # Извлечь rationale (обоснование)
    rationale_match = re.search(
        r"(?:ОБОСНОВАНИЕ|RATIONALE):\s*(.+?)(?:\n\n|\n[А-ЯA-Z]|$)",
        directive_text,
        re.IGNORECASE | re.DOTALL,
    )
    if rationale_match:
        structured["rationale"] = rationale_match.group(1).strip()
    else:
        # Если не найдено явное обоснование, берем весь текст как rationale
        structured["rationale"] = directive_text[:500].strip()

    # Извлечь risks
    risks_match = re.search(
        r"(?:РИСКИ|RISKS):\s*(.+?)(?:\n\n|\n[А-ЯA-Z]|$)", directive_text, re.IGNORECASE | re.DOTALL
    )
    if risks_match:
        risks_text = risks_match.group(1).strip()
        # Разбить на список по дефисам или цифрам
        risk_items = re.split(r"[-•]\s*|\d+\.\s*", risks_text)
        structured["risks"] = [r.strip() for r in risk_items if r.strip()]

    # Извлечь confidence
    confidence_match = re.search(
        r"(?:УВЕРЕННОСТЬ|CONFIDENCE):\s*([\d.]+)", directive_text, re.IGNORECASE
    )
    if confidence_match:
        try:
            structured["confidence"] = float(confidence_match.group(1))
        except Exception:
            pass

    # Проверка на рекомендацию подтверждения человеком
    if re.search(
        r"(?:ТРЕБУЕТ.*ПОДТВЕРЖДЕНИЯ|HUMAN.*REVIEW|ПОДТВЕРДИТЬ)", directive_text, re.IGNORECASE
    ):
        structured["recommend_human_review"] = True
    else:
        structured["recommend_human_review"] = False

    return structured


async def consult_board(
    question: str,
    context: Optional[dict] = None,
    correlation_id: Optional[str] = None,
    source: str = "api",
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Консультация Совета Директоров по единичному вопросу.

    Args:
        question: Вопрос пользователя/чата
        context: Дополнительный контекст (опционально)
        correlation_id: ID для трассировки запроса
        source: Источник запроса (chat, api, nightly, dashboard)
        session_id: ID сессии (для чата)
        user_id: ID пользователя (для чата)

    Returns:
        {"directive_text": str, "structured_decision": dict} или None при ошибке
    """
    allowed_sources = {"chat", "api", "nightly", "dashboard", "task_escalation"}
    source_raw = (source or "api").strip().lower()
    source = source_raw if source_raw in allowed_sources else "api"
    if source_raw != source:
        print(f"⚠️ Board consult source '{source_raw}' normalized to '{source}'")

    print(
        f"[{datetime.now()}] 🏛 BOARD CONSULT starting (source={source}, correlation_id={correlation_id})..."
    )

    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # 1. Сбор контекста
            okr_context = ""
            try:
                okrs = await conn.fetch("SELECT objective, department, period FROM okrs LIMIT 5")
                okr_context = (
                    "\n".join(
                        [f"- {o['objective']} ({o['department']}, {o['period']})" for o in okrs]
                    )
                    if okrs
                    else ""
                )
            except Exception as e:
                print(
                    f"⚠️ Не удалось получить OKR (таблица может отсутствовать или схема иная): {e}"
                )
                okr_context = ""

            tasks_context = ""
            try:
                tasks_stats = await conn.fetch(
                    "SELECT status, count(*) FROM tasks GROUP BY status LIMIT 10"
                )
                tasks_context = (
                    "\n".join([f"{t['status']}: {t['count']}" for t in tasks_stats])
                    if tasks_stats
                    else ""
                )
            except Exception as e:
                print(f"⚠️ Не удалось получить статус задач: {e}")
                tasks_context = ""

            # Последняя директива (для контекста)
            last_directive = ""
            try:
                last_dir_row = await conn.fetchrow("""
                    SELECT content FROM knowledge_nodes
                    WHERE metadata->>'type' = 'board_directive'
                    ORDER BY created_at DESC LIMIT 1
                """)
                if last_dir_row:
                    last_directive = last_dir_row["content"][:300] + "..."
            except Exception as e:
                print(f"⚠️ Не удалось получить последнюю директиву: {e}")

        # 2. Формирование промпта для Совета
        # Важно: без квадратных скобок-плейсхолдеров — слабые модели их копируют дословно.
        board_prompt = f"""
ВЫ - СОВЕТ ДИРЕКТОРОВ КОРПОРАЦИИ (CEO Владимир, Lead Виктория, CTO Дмитрий).

КОНТЕКСТ (фон, не подменяйте им ответ):
{f"OKR: {okr_context}" if okr_context else "OKR: не заданы"}
{f"Задачи: {tasks_context}" if tasks_context else "Задачи: нет данных"}
{f"Последняя директива: {last_directive}" if last_directive else ""}

ВОПРОС (отвечайте именно на него):
{question}

ЗАДАЧА: Примите стратегическое решение по ВОПРОСУ. OKR — только фон.
Без квадратных скобок и без плейсхолдеров. Формат:

РЕШЕНИЕ: конкретное действие на 24 часа одной фразой
ОБОСНОВАНИЕ: 2-3 предложения почему это отвечает на вопрос
РИСКИ: 2-3 конкретных риска и митигация
УВЕРЕННОСТЬ: число от 0.0 до 1.0

Если решение критично (архитектура/бюджет/сроки) и уверенность < 0.8, добавьте строку:
ТРЕБУЕТ ПОДТВЕРЖДЕНИЯ ЧЕЛОВЕКОМ
"""

        # 3. LLM: fast dialogue_llm first (API SLA), then bounded ai_core.
        consult_timeout = float(os.getenv("BOARD_CONSULT_TIMEOUT_SEC", "120"))
        fast_timeout = float(os.getenv("BOARD_CONSULT_FAST_TIMEOUT_SEC", "90"))
        fast_first = os.getenv("BOARD_CONSULT_FAST_FIRST", "true").lower() in (
            "1",
            "true",
            "yes",
        )
        # Quality default: phi3.5 (smollm2:360m copies template placeholders).
        consult_model = os.getenv("BOARD_CONSULT_MODEL", "phi3.5:3.8b")
        quality_model = os.getenv("BOARD_CONSULT_QUALITY_MODEL", consult_model)
        directive = None

        async def _via_dialogue_llm(prompt: str, *, model_hint: str) -> Optional[str]:
            try:
                from dialogue_llm import generate_dialogue, is_incomplete_text
            except ImportError:
                from knowledge_os.app.dialogue_llm import generate_dialogue, is_incomplete_text

            gen = await generate_dialogue(prompt, expert_name="Виктория", model_hint=model_hint)
            text = str(getattr(gen, "text", "") or "").strip()
            if not getattr(gen, "ok", False) or len(text) < 20:
                print(
                    f"⚠️ dialogue_llm miss: ok={getattr(gen, 'ok', None)} "
                    f"reason={getattr(gen, 'reason', None)} len={len(text)} model={model_hint}"
                )
                return None
            if is_stub_directive(text):
                print("⚠️ dialogue_llm returned stub markers")
                return None
            if is_incomplete_text(text) and len(text) < 60:
                print("⚠️ dialogue_llm incomplete/short")
                return None
            if is_low_quality_directive(text):
                print("⚠️ dialogue_llm low-quality / prompt-echo rejected")
                return None
            return text

        async def _via_ai_core() -> Optional[str]:
            try:
                from ai_core import run_smart_agent_async

                async def board_llm_call():
                    return await run_smart_agent_async(
                        board_prompt,
                        expert_name="Совет Директоров",
                        category="reasoning",
                        is_critical=True,
                        is_vip=False,
                    )

                if _mlx_queue and RequestPriority:
                    print("🏛️ [BOARD] Запрос с HIGH приоритетом через MLX Queue...")
                    success, request_id, position = await _mlx_queue.add_request(
                        priority=RequestPriority.HIGH,
                        callback=board_llm_call,
                        timeout=consult_timeout,
                        metadata={"source": source, "correlation_id": correlation_id},
                    )
                    if success:
                        print(
                            f"✅ [BOARD] Запрос в очереди (ID: {request_id}, позиция: {position})"
                        )
                    else:
                        print("⚠️ [BOARD] Очередь переполнена, прямой вызов...")

                text = await asyncio.wait_for(board_llm_call(), timeout=consult_timeout)
                text = str(text or "").strip()
                if text and not is_low_quality_directive(text):
                    return text
                if text:
                    print("⚠️ ai_core returned low-quality directive")
                return None
            except ImportError:
                print("⚠️ ai_core не доступен")
                return None
            except asyncio.TimeoutError:
                print(f"⚠️ Board consult ai_core timeout after {consult_timeout:.0f}s")
                return None
            except Exception as e:
                print(f"⚠️ Board consult ai_core failed: {e}")
                return None

        compact_prompt = (
            f"Вопрос Совета Директоров: {question}\n\n"
            "Ответь строго по делу, БЕЗ квадратных скобок и БЕЗ плейсхолдеров.\n"
            "Формат:\n"
            "РЕШЕНИЕ: конкретное решение одной фразой\n"
            "ОБОСНОВАНИЕ: 2-3 предложения по сути вопроса\n"
            "РИСКИ: 2-3 коротких риска\n"
            "УВЕРЕННОСТЬ: число от 0.0 до 1.0\n"
        )

        if fast_first:
            try:
                directive = await asyncio.wait_for(
                    _via_dialogue_llm(board_prompt, model_hint=consult_model),
                    timeout=fast_timeout,
                )
                if directive:
                    print(f"✅ Board consult via dialogue_llm (fast-first, {consult_model})")
            except asyncio.TimeoutError:
                print(f"⚠️ Board consult dialogue_llm timeout after {fast_timeout:.0f}s")
            except Exception as e:
                print(f"⚠️ Board consult dialogue_llm failed: {e}")

        if is_low_quality_directive(directive):
            print("⚠️ Board consult quality gate; compact retry on quality model")
            try:
                text2 = await asyncio.wait_for(
                    _via_dialogue_llm(compact_prompt, model_hint=quality_model),
                    timeout=fast_timeout,
                )
                if text2:
                    directive = text2
                    print(f"✅ Board consult compact retry accepted ({quality_model})")
            except Exception as e:
                print(f"⚠️ Board consult compact retry failed: {e}")

        if is_low_quality_directive(directive):
            print("⚠️ Board consult escalating to ai_core for quality")
            text3 = await _via_ai_core()
            if text3:
                directive = text3
                print("✅ Board consult via ai_core")

        # Last resort: compact on quality model again after heavy path.
        if is_low_quality_directive(directive):
            try:
                text4 = await asyncio.wait_for(
                    _via_dialogue_llm(compact_prompt, model_hint=quality_model),
                    timeout=fast_timeout,
                )
                if text4:
                    directive = text4
                    print("✅ Board consult via dialogue_llm (last resort quality)")
            except Exception as e:
                print(f"⚠️ Board consult last-resort dialogue_llm failed: {e}")

        if is_low_quality_directive(directive):
            print("❌ Совет отклонил low-quality/prompt-echo директиву (fail-closed)")
            return None
        directive = str(directive).strip()

        # 4. Парсинг структуры
        structured_decision = parse_directive_structure(directive)

        # Определение risk_level на основе ключевых слов и confidence
        risk_level = "low"
        directive_lower = directive.lower()
        if any(
            word in directive_lower
            for word in ["архитектура", "бюджет", "критичн", "серьезн", "риск"]
        ):
            risk_level = "high"
        elif any(word in directive_lower for word in ["важн", "изменен", "рефактор", "переработ"]):
            risk_level = "medium"

        if structured_decision.get("confidence", 1.0) < 0.7:
            risk_level = "high"  # Низкая уверенность = высокий риск

        recommend_human_review = structured_decision.get("recommend_human_review", False)
        if risk_level == "high" or structured_decision.get("confidence", 1.0) < 0.7:
            recommend_human_review = True

        # 5. Сохранение в board_decisions (используем pool.acquire() снова)
        context_snapshot = {
            "okr": okr_context[:500] if okr_context else "",
            "tasks": tasks_context[:300] if tasks_context else "",
            "last_directive": last_directive[:200] if last_directive else "",
        }

        # 5b. Durable Markdown first (must not depend on DB write success).
        _publish_board_markdown(
            directive=directive,
            okr_context=okr_context,
            tasks_context=tasks_context,
            title="КОНСУЛЬТАЦИЯ СОВЕТА ДИРЕКТОРОВ",
        )

        # 6. Persist to board_decisions + optional knowledge_nodes (best-effort).
        try:
            pool = await get_db_pool()
            async with pool.acquire() as write_conn:
                await write_conn.execute(
                    """
                    INSERT INTO board_decisions (
                        source, correlation_id, session_id, user_id, question, context_snapshot,
                        directive_text, structured_decision, risk_level, recommend_human_review
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                    source,
                    correlation_id,
                    session_id,
                    user_id,
                    question,
                    json.dumps(context_snapshot),
                    directive,
                    json.dumps(structured_decision),
                    risk_level,
                    recommend_human_review,
                )

                try:
                    domain_id = await write_conn.fetchval(
                        "SELECT id FROM domains WHERE name = 'Management' LIMIT 1"
                    )
                    if domain_id:
                        content_kn = f"🏛 Консультация Совета: {structured_decision.get('decision', '')[:100]}"
                        meta_kn = json.dumps(
                            {
                                "type": "board_consult",
                                "correlation_id": correlation_id,
                                "date": datetime.now().isoformat(),
                            }
                        )
                        conf = structured_decision.get("confidence", 0.8)
                        embedding = None
                        # Default OFF: embedding can block the event loop under Ollama/MLX load
                        # and stall HTTP even after directive+MD+DB are done.
                        if os.getenv("BOARD_KN_EMBED", "0").lower() in (
                            "1",
                            "true",
                            "yes",
                        ):
                            try:
                                from semantic_cache import get_embedding

                                emb_timeout = float(os.getenv("BOARD_KN_EMBED_TIMEOUT_SEC", "8"))
                                embedding = await asyncio.wait_for(
                                    get_embedding(content_kn[:8000]), timeout=emb_timeout
                                )
                            except asyncio.TimeoutError:
                                print("⚠️ Board KN embedding timeout; saving node without embedding")
                            except Exception:
                                pass
                        if embedding is not None:
                            await write_conn.execute(
                                """
                                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                                VALUES ($1, $2, $3, $4, true, $5::vector)
                            """,
                                domain_id,
                                content_kn,
                                conf,
                                meta_kn,
                                str(embedding),
                            )
                        else:
                            await write_conn.execute(
                                """
                                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                                VALUES ($1, $2, $3, $4, true)
                            """,
                                domain_id,
                                content_kn,
                                conf,
                                meta_kn,
                            )
                except Exception as e:
                    print(f"⚠️ Не удалось сохранить узел в knowledge_nodes: {e}")
        except Exception as e:
            print(f"⚠️ Не удалось сохранить board_decisions (ответ всё равно возвращаем): {e}")

        print(
            f"✅ Board consult completed: decision='{structured_decision.get('decision', '')[:50]}...', risk={risk_level}, recommend_review={recommend_human_review}"
        )

        return {
            "directive_text": directive,
            "structured_decision": structured_decision,
            "risk_level": risk_level,
            "recommend_human_review": recommend_human_review,
        }

    except Exception as e:
        print(f"❌ Board consult error: {e}")
        import traceback

        traceback.print_exc()
        return None


async def run_board_simulation(conn, proposed_goal: str) -> dict[str, Any]:
    """[Strategic Simulator] Прогон цели через исторические данные и экспертов."""
    print(f"🚀 [SIMULATOR] Запуск симуляции для цели: {proposed_goal}")

    # 1. Сбор исторических данных об успехах/ошибках
    stats = await conn.fetchrow("""
        SELECT
            AVG(feedback_score) as avg_score,
            COUNT(*) FILTER (WHERE metadata->>'error' IS NOT NULL) as error_count,
            COUNT(*) as total_tasks
        FROM interaction_logs
        WHERE created_at > NOW() - INTERVAL '30 days'
    """)

    # 2. Промпт для симуляции
    sim_prompt = f"""
    ВЫ - СТРАТЕГИЧЕСКИЙ СИМУЛЯТОР Singularity 10.0.
    ПРЕДЛОЖЕННАЯ ЦЕЛЬ: {proposed_goal}

    ИСТОРИЧЕСКИЙ КОНТЕКСТ (30 дней):
    - Средний фидбек: {stats["avg_score"] or "N/A"}
    - Ошибок: {stats["error_count"]} из {stats["total_tasks"]} задач

    ЗАДАЧА: Спрогнозируйте вероятность успеха (0-100%) и выявите 2 критических узких места.
    ОТВЕТЬТЕ В JSON: {{"probability": 85, "bottlenecks": ["...", "..."], "recommendation": "..."}}
    """

    from ai_core import run_smart_agent_async

    result = await run_smart_agent_async(
        sim_prompt, expert_name="Симулятор", category="reasoning", is_vip=True
    )

    try:
        # Очистка и парсинг
        if "```" in result:
            result = result.split("```")[1].replace("json", "").strip()
        return json.loads(result)
    except Exception:
        return {
            "probability": 50,
            "bottlenecks": ["Не удалось провести точный расчет"],
            "recommendation": "Требуется ручной анализ",
        }


async def run_board_meeting():
    print(f"[{datetime.now()}] 🏛 STRATEGIC BOARD OF DIRECTORS MEETING starting...")

    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # 1. Сбор данных для заседания
            # - Текущие OKR
            okr_context = ""
            try:
                okrs = await conn.fetch("SELECT objective, department, period FROM okrs")
                okr_context = (
                    "\n".join(
                        [f"- {o['objective']} ({o['department']}, {o['period']})" for o in okrs]
                    )
                    if okrs
                    else ""
                )
            except Exception as e:
                print(
                    f"⚠️ Не удалось получить OKR (таблица может отсутствовать или схема иная): {e}"
                )
                okr_context = ""

            # - Новые знания за 24 часа
            insights_context = ""
            try:
                new_insights = await conn.fetch("""
                    SELECT k.content, d.name as domain
                    FROM knowledge_nodes k
                    JOIN domains d ON k.domain_id = d.id
                    WHERE k.created_at > NOW() - INTERVAL '24 hours'
                    LIMIT 50
                """)
                insights_context = (
                    "\n".join([f"[{i['domain']}] {i['content'][:200]}..." for i in new_insights])
                    if new_insights
                    else ""
                )
            except Exception as e:
                print(f"⚠️ Не удалось получить знания: {e}")
                insights_context = ""

            # - Статус задач
            tasks_context = ""
            try:
                tasks_stats = await conn.fetch("SELECT status, count(*) FROM tasks GROUP BY status")
                tasks_context = (
                    "\n".join([f"{t['status']}: {t['count']}" for t in tasks_stats])
                    if tasks_stats
                    else ""
                )
            except Exception as e:
                print(f"⚠️ Не удалось получить статус задач: {e}")
                tasks_context = ""

            # 2–3. Sync Victoria + stub reject + local fallback (no raw KB dump in goal)
            directive = await _call_victoria_board_directive(
                okr_summary=_summarize_context(okr_context, limit=350),
                tasks_summary=_summarize_context(tasks_context, limit=250),
                insights_summary=_summarize_context(insights_context, limit=350),
            )

            if directive:
                print(f"✅ ДИРЕКТИВА ПОЛУЧЕНА ({len(directive)} chars)")

            # [SINGULARITY 31.3] Фильтр: HTML / queue stubs / ошибки
            if directive and (
                "<" in directive
                and ">" in directive
                and ("<!DOCTYPE" in directive or "<html" in directive or "<body" in directive)
            ):
                print("⚠️ LLM вернул HTML вместо директивы")
                directive = None
            if directive and is_stub_directive(directive):
                print("⚠️ Отклонена stub-директива (queue ack), сохранение пропущено")
                directive = None

            if (
                directive
                and len(directive) > 40
                and "Ошибка" not in directive
                and "❌" not in directive
                and not is_stub_directive(directive)
            ):
                # 4. Парсинг структуры
                structured_decision = parse_directive_structure(directive)

                # 5. Сохранение в board_decisions (новое!)
                context_snapshot = {
                    "okr": okr_context[:500] if okr_context else "",
                    "insights": insights_context[:500] if insights_context else "",
                    "tasks": tasks_context[:300] if tasks_context else "",
                }

                try:
                    await conn.execute(
                        """
                        INSERT INTO board_decisions (
                            source, question, context_snapshot, directive_text,
                            structured_decision, risk_level
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                        "nightly",
                        "Daily Strategic Board Meeting",
                        json.dumps(context_snapshot),
                        directive,
                        json.dumps(structured_decision),
                        "medium",
                    )
                    print("✅ Директива сохранена в board_decisions")
                except Exception as e:
                    print(f"⚠️ Не удалось сохранить в board_decisions: {e}")

                # 6. Сохраняем директиву в спец. узел знаний (Domain: Management); по возможности с embedding (VERIFICATION §5)
                try:
                    domain_id = await conn.fetchval(
                        "SELECT id FROM domains WHERE name = 'Management'"
                    )
                    if domain_id:
                        content_kn = f"🏛 СТРАТЕГИЧЕСКАЯ ДИРЕКТИВА СОВЕТА: {directive}"
                        meta_kn = json.dumps(
                            {"type": "board_directive", "date": datetime.now().isoformat()}
                        )
                        embedding = None
                        try:
                            from semantic_cache import get_embedding

                            embedding = await get_embedding(content_kn[:8000])
                        except Exception:
                            pass
                        if embedding is not None:
                            await conn.execute(
                                """
                                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                                VALUES ($1, $2, 1.0, $3, true, $4::vector)
                            """,
                                domain_id,
                                content_kn,
                                meta_kn,
                                str(embedding),
                            )
                        else:
                            await conn.execute(
                                """
                                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                                VALUES ($1, $2, 1.0, $3, true)
                            """,
                                domain_id,
                                content_kn,
                                meta_kn,
                            )
                except Exception as e:
                    print(f"⚠️ Не удалось сохранить в knowledge_nodes: {e}")

                # 7. Также сохраняем в дебаты для истории - как было
                try:
                    await conn.execute(
                        """
                        INSERT INTO expert_discussions (topic, consensus_summary, status)
                        VALUES ('Daily Strategic Board Meeting', $1, 'closed')
                    """,
                        directive,
                    )
                except Exception as e:
                    print(f"⚠️ Не удалось сохранить в expert_discussions: {e}")

                print("✅ Strategic Directive issued and stored.")

                # 8. Публикация в Markdown для истории (Singularity 10.0: Transparency)
                _publish_board_markdown(
                    directive=directive,
                    okr_context=okr_context,
                    tasks_context=tasks_context,
                )
            else:
                print("❌ Директива не получена или содержит ошибку. Сохранение пропущено.")

    except Exception as e:
        print(f"❌ Board meeting error: {e}")
        import traceback

        traceback.print_exc()
    print(f"[{datetime.now()}] Strategic Board Meeting finished.")


if __name__ == "__main__":
    asyncio.run(run_board_meeting())
