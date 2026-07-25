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

# Models copy numbered template lines as "1) первое действие" / "первый фокус".
_TEMPLATE_ACTION_RE = re.compile(
    r"(?:^|\n)\s*\d+\)\s*(?:перв|втор|треть|четв|пят)"
    r"(?:ое|ый|ий|ая)?\s+(?:действие|фокус)\b"
    r"|(?:^|\n)\s*действия:\s*$",
    re.IGNORECASE | re.MULTILINE,
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
    if _TEMPLATE_ACTION_RE.search(t) or "первое действие" in low or "первый фокус" in low:
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
    # Mixed-language / prompt-leak garbage (seen under model pressure).
    if re.search(
        r"\b(bitte|please provide|as an ai|i cannot|you provide a ques)\b",
        low,
    ):
        return True
    return False


_QUESTION_STOPWORDS = {
    "нужно",
    "надо",
    "стоит",
    "сейчас",
    "какой",
    "какая",
    "какие",
    "каков",
    "ли",
    "или",
    "что",
    "чтобы",
    "для",
    "при",
    "уже",
    "ещё",
    "еще",
    "как",
    "это",
    "этой",
    "этом",
    "есть",
    "быть",
    "были",
    "будет",
    "дай",
    "конкретное",
    "конкретный",
    "сутки",
    "часа",
    "час",
    "перед",
    "после",
    "про",
    "нас",
    "нам",
    "все",
    "всё",
    "the",
    "and",
    "for",
    "with",
    "from",
    "should",
    "would",
    "could",
    "about",
    "what",
    "when",
    "where",
    "which",
    "does",
    "did",
    "are",
    "was",
    "were",
    "have",
    "has",
    "been",
}


def extract_question_intent_terms(question: str, *, limit: int = 12) -> list[str]:
    """Content tokens from the user question (ru/en), minus stopwords."""
    q = (question or "").lower()
    raw = re.findall(r"[a-zа-яё0-9_]{4,}", q, flags=re.IGNORECASE)
    terms: list[str] = []
    seen: set[str] = set()
    for tok in raw:
        t = tok.lower()
        if t in _QUESTION_STOPWORDS or t.isdigit():
            continue
        if t in seen:
            continue
        seen.add(t)
        terms.append(t)
        if len(terms) >= limit:
            break
    return terms


# Too common in OKR-drift answers — alone they do not prove intent match.
_GENERIC_INTENT_TERMS = {
    "ollama",
    "модели",
    "модел",
    "model",
    "models",
    "совета",
    "советом",
    "заседанием",
    "заседание",
    "studio",
    "knowledge",
    "корпорац",
    "систем",
    "среды",
    "среде",
    "внедрен",
    "производ",
    "daily",
    "strategic",
    "board",
    "meeting",
}


# If question triggers a family, answer must reflect that family (anti OKR-drift / anti wrong polarity).
_INTENT_FAMILIES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("разгруж", "разгруз", "выгруз", "unload"),
        (
            "разгруз",
            "выгруз",
            "unload",
            "keep_alive",
            "освобод",
            "не держать",
            "нагруз",
            "памят",
            "vram",
            "конкуренц",
        ),
    ),
    (
        ("оставить", "истори"),
        ("оставить", "истори", "не масс", "не сбрас", "не reset", "без reset", "не трог"),
    ),
    (
        ("стабильн", "стабил"),
        ("стабил", "надеж", "uptime", "sla", "health", "нагруз", "памят"),
    ),
)


def directive_matches_question_intent(
    question: str, directive: Optional[str], *, min_hits: int = 1
) -> bool:
    """
    True if decision/rationale reflects the question (not generic OKR drift).
    Skips gate when the question has too few content terms (e.g. nightly title).
    Prefer hits on discriminative terms (e.g. разгружать), not only ollama/модели.
    """
    q_low = (question or "").lower()
    terms = extract_question_intent_terms(question)
    specific = [t for t in terms if t not in _GENERIC_INTENT_TERMS]
    if len(specific) < 1:
        return True  # nightly/generic titles — do not false-reject
    text = (directive or "").strip()
    if not text:
        return False
    focus_parts = []
    for label in ("решение", "decision", "обоснование", "rationale"):
        m = re.search(
            rf"(?:{label}):\s*(.+?)(?:\n(?:[А-ЯA-Z]{{2,}}|\w+:)|\Z)",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if m:
            focus_parts.append(m.group(1))
    focus = " ".join(focus_parts) if focus_parts else text
    focus_l = focus.lower()

    def _has_term(hay: str, needle: str) -> bool:
        # Left boundary only: 'разгруз'→'разгрузка', but not 'оставить' inside 'предоставить'.
        return re.search(rf"(?<![a-zа-яё]){re.escape(needle)}", hay) is not None

    # Family constraints first (unload / leave-history / stability).
    for q_keys, a_keys in _INTENT_FAMILIES:
        if any(_has_term(q_low, k) or k in q_low for k in q_keys):
            if not any(_has_term(focus_l, k) for k in a_keys):
                return False

    hits = sum(1 for t in specific if _has_term(focus_l, t) or t in focus_l)
    need = min_hits if len(specific) <= 3 else min(2, min_hits + 1)
    return hits >= need


def _summarize_context(raw: str, *, limit: int = 400) -> str:
    """Compact context for the board prompt — avoid dumping raw KB (CODE-queue trap)."""
    text = re.sub(r"\s+", " ", (raw or "").strip())
    if not text:
        return "нет данных"
    # Neutralize common CODE-queue triggers inside embedded context.
    text = re.sub(r"\bcode\b", "software", text, flags=re.IGNORECASE)
    text = text.replace("код", "ПО")
    return text[:limit]


async def _maybe_unload_heavy_ollama(*, keep_models: list[str]) -> None:
    """
    Best-effort: unload idle heavy Ollama models so board teacher is not starved.
    Controlled by BOARD_CONSULT_UNLOAD_HEAVY (default true).
    """
    if os.getenv("BOARD_CONSULT_UNLOAD_HEAVY", "true").lower() not in (
        "1",
        "true",
        "yes",
    ):
        return
    base = (
        os.getenv("OLLAMA_BASE_URL")
        or os.getenv("OLLAMA_URL")
        or "http://host.docker.internal:11434"
    ).rstrip("/")
    keep = {m.lower() for m in keep_models if m}
    keep_bases = {m.split(":")[0].lower() for m in keep}
    try:
        import httpx

        async with httpx.AsyncClient(timeout=12.0) as client:
            ps = await client.get(f"{base}/api/ps")
            if ps.status_code != 200:
                return
            loaded = [m.get("name", "") for m in (ps.json() or {}).get("models", [])]
            for name in loaded:
                n = (name or "").lower()
                if not n:
                    continue
                if n in keep or n.split(":")[0] in keep_bases:
                    continue
                # Keep small teacher / board models; unload the rest.
                try:
                    await client.post(
                        f"{base}/api/generate",
                        json={"model": name, "prompt": "", "keep_alive": 0},
                    )
                    print(f"🧹 Board unload idle Ollama model: {name}")
                except Exception:
                    pass
    except Exception as e:
        print(f"⚠️ Board Ollama unload skipped: {e}")


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

Сформулируй ДИРЕКТИВУ СОВЕТА строго в формате (без квадратных скобок и плейсхолдеров).
Не копируй слова «первое/второе действие» и не оставляй пустые нумерованные строки.
Формат:
РЕШЕНИЕ: главное направление на 24 часа одной фразой
ОБОСНОВАНИЕ: почему это важно (2-3 предложения)
РИСКИ: список конкретных рисков
УВЕРЕННОСТЬ: число от 0.0 до 1.0
"""
    timeout = float(os.getenv("BOARD_VICTORIA_TIMEOUT_SEC", "480"))
    board_model = os.getenv("BOARD_CONSULT_MODEL", "victoria-wisdom-v3.5")
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
                from okr_service import fetch_active_okrs, format_okr_context, get_active_okr_period

                okrs = await fetch_active_okrs(conn, limit=5)
                okr_context = format_okr_context(okrs)
                if not okr_context:
                    okr_context = f"(нет OKR за период {get_active_okr_period()})"
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
                    candidate = (last_dir_row["content"] or "")[:300]
                    # Do not seed the next meeting with template garbage (self-reinforcing).
                    clow = candidate.lower()
                    if (
                        "первое действие" in clow
                        or "первый фокус" in clow
                        or _TEMPLATE_ACTION_RE.search(candidate)
                    ):
                        last_directive = ""
                    else:
                        last_directive = candidate + "..."
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
        # Victoria-first (MLX brain). phi3.5 only as last-resort fallback.
        use_mlx = os.getenv("BOARD_CONSULT_USE_MLX", "true").lower() in (
            "1",
            "true",
            "yes",
        )
        mlx_model_hint = os.getenv("BOARD_CONSULT_MLX_MODEL", "victoria-wisdom-v3.5")
        consult_model = os.getenv("BOARD_CONSULT_MODEL", mlx_model_hint)
        quality_model = os.getenv("BOARD_CONSULT_QUALITY_MODEL", "victoria-wisdom-v3.5:latest")
        fallback_model = os.getenv("BOARD_CONSULT_FALLBACK_MODEL", "phi3.5:3.8b")
        # No-colon hint → dialogue_llm prefers MLX (Victoria brain, usually warm).
        if use_mlx and consult_model.replace(":latest", "").startswith("victoria-wisdom"):
            primary_hint = mlx_model_hint
        else:
            primary_hint = consult_model
        intent_terms = extract_question_intent_terms(question)
        intent_specific = [t for t in intent_terms if t not in _GENERIC_INTENT_TERMS]
        enforce_intent = source in {"api", "chat", "dashboard"} and len(intent_specific) >= 1

        await _maybe_unload_heavy_ollama(
            keep_models=[
                consult_model,
                quality_model,
                fallback_model,
                mlx_model_hint,
                "victoria-wisdom-v3.5",
                "victoria-wisdom-v3.5:latest",
                "phi3.5:3.8b",
            ]
        )

        directive = None

        def _acceptable(text: Optional[str]) -> bool:
            if is_low_quality_directive(text):
                return False
            if enforce_intent and not directive_matches_question_intent(question, text):
                return False
            return True

        async def _via_dialogue_llm(prompt: str, *, model_hint: str) -> Optional[str]:
            try:
                from dialogue_llm import generate_dialogue, is_incomplete_text
            except ImportError:
                from knowledge_os.app.dialogue_llm import generate_dialogue, is_incomplete_text

            # Prefer MLX for quality hints when enabled (no colon → MLX-only).
            # Do not fall through to Ollama inside the same wait_for budget.
            prefer_mlx_only = use_mlx and (":" not in model_hint)
            backends = ("mlx",) if prefer_mlx_only else ("ollama",)
            gen = await generate_dialogue(
                prompt,
                expert_name="Виктория",
                model_hint=model_hint,
                backends=backends,
            )

            text = str(getattr(gen, "text", "") or "").strip()
            if not getattr(gen, "ok", False) or len(text) < 20:
                print(
                    f"⚠️ dialogue_llm miss: ok={getattr(gen, 'ok', None)} "
                    f"reason={getattr(gen, 'reason', None)} len={len(text)} "
                    f"model={model_hint} backends={backends}"
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

                ai_timeout = float(os.getenv("BOARD_CONSULT_AICORE_TIMEOUT_SEC", "45"))
                text = await asyncio.wait_for(board_llm_call(), timeout=ai_timeout)
                text = str(text or "").strip()
                if text and _acceptable(text):
                    return text
                if text and not is_low_quality_directive(text):
                    # Form OK but intent miss — still return for further retries.
                    return text
                if text:
                    print("⚠️ ai_core returned low-quality directive")
                return None
            except ImportError:
                print("⚠️ ai_core не доступен")
                return None
            except asyncio.TimeoutError:
                print(
                    f"⚠️ Board consult ai_core timeout after "
                    f"{float(os.getenv('BOARD_CONSULT_AICORE_TIMEOUT_SEC', '45')):.0f}s"
                )
                return None
            except Exception as e:
                print(f"⚠️ Board consult ai_core failed: {e}")
                return None

        intent_hint = ", ".join(intent_terms[:8]) if intent_terms else ""
        compact_prompt = (
            f"Вопрос Совета Директоров: {question}\n\n"
            f"Ключевые слова вопроса (обязательно отрази в РЕШЕНИЕ/ОБОСНОВАНИЕ): {intent_hint}\n"
            "Ответь ИМЕННО на этот вопрос. Не подменяй ответ общими OKR про «внедрение Ollama».\n"
            "Если в вопросе есть альтернатива (A или B) — явно выбери одну сторону "
            "и повтори её словами из вопроса (например: «оставить как историю», "
            "«разгружать тяжёлые модели»).\n"
            "БЕЗ квадратных скобок и БЕЗ плейсхолдеров.\n"
            "Формат:\n"
            "РЕШЕНИЕ: конкретное решение одной фразой по вопросу\n"
            "ОБОСНОВАНИЕ: 2-3 предложения по сути вопроса\n"
            "РИСКИ: 2-3 коротких риска\n"
            "УВЕРЕННОСТЬ: число от 0.0 до 1.0\n"
        )

        async def _compact_retry(model_hint: str, *, label: str) -> Optional[str]:
            try:
                text = await asyncio.wait_for(
                    _via_dialogue_llm(compact_prompt, model_hint=model_hint),
                    timeout=fast_timeout,
                )
                if text and _acceptable(text):
                    print(f"✅ Board consult {label} accepted ({model_hint})")
                    return text
                if text and not is_low_quality_directive(text):
                    print(f"⚠️ Board consult {label} form-ok intent-weak ({model_hint})")
                    return text
                return None
            except asyncio.TimeoutError:
                print(f"⚠️ Board consult {label} timeout after {fast_timeout:.0f}s")
                return None
            except Exception as e:
                print(f"⚠️ Board consult {label} failed: {type(e).__name__}: {e}")
                return None

        # Victoria-first: for interactive sources use compact (intent-anchored) before
        # the long OKR board_prompt — avoids 90s MLX timeouts that fall through to phi.
        prefer_compact_first = enforce_intent and source in {"api", "chat", "dashboard"}

        if fast_first and prefer_compact_first:
            directive = await _compact_retry(primary_hint, label="victoria-first")
            if not _acceptable(directive):
                try:
                    full = await asyncio.wait_for(
                        _via_dialogue_llm(board_prompt, model_hint=primary_hint),
                        timeout=fast_timeout,
                    )
                    if full and _acceptable(full):
                        directive = full
                        print(
                            f"✅ Board consult via dialogue_llm (victoria-first-full, {primary_hint})"
                        )
                    elif full:
                        directive = full
                        print("⚠️ Board consult victoria-first-full intent miss; will retry")
                except asyncio.TimeoutError:
                    print(f"⚠️ Board consult dialogue_llm timeout after {fast_timeout:.0f}s")
                except Exception as e:
                    print(f"⚠️ Board consult dialogue_llm failed: {e}")
        elif fast_first:
            try:
                directive = await asyncio.wait_for(
                    _via_dialogue_llm(board_prompt, model_hint=primary_hint),
                    timeout=fast_timeout,
                )
                if directive and _acceptable(directive):
                    print(f"✅ Board consult via dialogue_llm (victoria-first, {primary_hint})")
                elif directive:
                    print("⚠️ Board consult victoria-first intent miss; will retry")
            except asyncio.TimeoutError:
                print(f"⚠️ Board consult dialogue_llm timeout after {fast_timeout:.0f}s")
            except Exception as e:
                print(f"⚠️ Board consult dialogue_llm failed: {e}")

        if not _acceptable(directive):
            print("⚠️ Board consult quality/intent gate; compact retry")
            # Compact ladder: MLX Victoria → Ollama Victoria → phi3.5 (skip hint already tried).
            retry_plan: list[tuple[str, str]] = []
            if use_mlx:
                retry_plan.append((mlx_model_hint, "compact-mlx"))
            retry_plan.append((quality_model, "compact-ollama-victoria"))
            retry_plan.append((fallback_model, "compact-fallback-phi"))
            seen_hints: set[str] = set()
            if prefer_compact_first and primary_hint:
                seen_hints.add(primary_hint)
            for hint, label in retry_plan:
                if not hint or hint in seen_hints:
                    continue
                seen_hints.add(hint)
                text2 = await _compact_retry(hint, label=label)
                if text2 and _acceptable(text2):
                    directive = text2
                    break
                if text2:
                    directive = text2  # keep best form for next stage

        skip_aicore = os.getenv("BOARD_CONSULT_SKIP_AICORE", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        if not _acceptable(directive) and not skip_aicore:
            print("⚠️ Board consult escalating to ai_core for quality/intent")
            text3 = await _via_ai_core()
            if text3:
                directive = text3
                print("✅ Board consult via ai_core")

        if not _acceptable(directive):
            text4 = await _compact_retry(fallback_model, label="last-resort-phi")
            if text4:
                directive = text4

        if is_low_quality_directive(directive):
            print("❌ Совет отклонил low-quality/prompt-echo директиву (fail-closed)")
            return None
        if enforce_intent and not directive_matches_question_intent(question, directive):
            # Fail-closed for chat/api: do not publish OKR-drift as a real decision.
            print("❌ Совет отклонил директиву без попадания в вопрос (intent fail-closed)")
            return None
        directive = str(directive).strip()

        # 4. Парсинг структуры
        structured_decision = parse_directive_structure(directive)

        # risk_level: score decision/rationale only (ignore the РИСКИ: label itself).
        risk_level = "low"
        focus_for_risk = (
            f"{structured_decision.get('decision', '')} {structured_decision.get('rationale', '')}"
        ).lower()
        if any(
            word in focus_for_risk
            for word in ["архитектура", "бюджет", "критичн", "серьезн", "безопасн"]
        ):
            risk_level = "high"
        elif any(word in focus_for_risk for word in ["важн", "изменен", "рефактор", "переработ"]):
            risk_level = "medium"

        if structured_decision.get("confidence", 1.0) < 0.7:
            risk_level = "high"

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
            # - Текущие OKR (только active period — Grove/Doerr: не тащить архив)
            okr_context = ""
            try:
                from okr_service import (
                    fetch_active_okrs,
                    format_okr_context,
                    get_active_okr_period,
                    refresh_key_results_from_metrics,
                )

                try:
                    await refresh_key_results_from_metrics(conn)
                except Exception as re:
                    print(f"⚠️ OKR metrics refresh skipped: {re}")
                okrs = await fetch_active_okrs(conn)
                okr_context = format_okr_context(okrs)
                if not okr_context:
                    okr_context = f"(нет OKR за период {get_active_okr_period()})"
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
