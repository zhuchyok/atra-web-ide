"""
Expert DNA Wisdom Injection (план 2026-09-22, Фаза 5.2). v2 — цель: experts.metadata.wisdom_dna.

Замкнутый цикл «работа → дистилляция → эксперт стал умнее»:
  1. Отбор high-band wisdom (distilled + band=high + confidence>=0.8, без маркера инъекции).
  2. Кураторский маппинг категория → эксперт (жёсткая таблица, без фуззи).
  3. Инъекция: experts.metadata.wisdom_dna (JSONB) — подхватывается _compose_expert_prompt
     (все LLM-пути через get_expert_system_prompt), без перезапусков.
  4. Eval до/после через /run API Виктории (боевой маршрут) с персоной эксперта;
     вердикт судьи victoria-wisdom-24k (MLX). Деградация → автороллбэк (восстановление
     предыдущего wisdom_dna из истории в metadata.wisdom_dna_history).

Гейты: experts.auto_dna_sync=TRUE; ≤800 символов; env DNA_INJECTION_ENABLED=false выключает всё.
"""

import asyncio
import json
import logging
import os
import time
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg
import httpx

logger = logging.getLogger("dna_injection")

MAX_WISDOM_DNA_CHARS = 800
MAX_EXPERTS_PER_CYCLE = int(os.getenv("DNA_INJECTION_MAX_EXPERTS", "1"))
EVAL_QUESTIONS = int(os.getenv("DNA_INJECTION_EVAL_QUESTIONS", "2"))
RUN_TIMEOUT = int(os.getenv("DNA_INJECTION_RUN_TIMEOUT", "180"))

CATEGORY_TO_EXPERT: List[tuple[str, str]] = [
    ("тест", "Анна"),
    ("qa", "Анна"),
    ("testing", "Анна"),
    ("безопас", "Алексей"),
    ("security", "Алексей"),
    ("модель", "Дмитрий"),
    ("ml", "Дмитрий"),
    ("database", "Роман"),
    ("бд", "Роман"),
    ("postgres", "Роман"),
    ("код", "Игорь"),
    ("coding", "Игорь"),
    ("code", "Игорь"),
    ("devops", "Сергей"),
    ("ops", "Сергей"),
    ("инфраструк", "Сергей"),
    ("research", "Виктория"),
    ("strategy", "Виктория"),
    ("стратег", "Виктория"),
    ("управлен", "Виктория"),
]

EXPERT_EVAL_QUESTIONS: Dict[str, List[str]] = {
    "Виктория": [
        "какая стратегия приоритизации задач команды наиболее устойчива к сбоям?",
        "как удерживать баланс между автономией роя и качеством ответов?",
    ],
    "Анна": [
        "Как правильно оформить юнит-тест для функции с побочными эффектами?",
        "Как проверить, что API-эндпоинт готов к продакшену?",
    ],
    "Алексей": [
        "Где хранить API-ключи в проекте и чего избегать?",
        "Как проверить промпт на устойчивость к prompt injection?",
    ],
    "Дмитрий": [
        "Когда выбирать fine-tuning вместо few-shot промптинга?",
        "Что важнее для локальной модели: квантование или контекстное окно?",
    ],
    "Роман": [
        "Когда HNSW-индекс оправдан в PostgreSQL?",
        "Чем опасен пул соединений без лимитов?",
    ],
    "Игорь": [
        "Как безопасно проводить рефакторинг большого модуля?",
        "Что проверить перед код-ревью чужого PR?",
    ],
    "Сергей": [
        "Какая стратегия бэкапов БД считается достаточной?",
        "Что проверить в healthcheck контейнера на slim-образе?",
    ],
}

VICTORIA_URL = os.getenv("VICTORIA_URL", "http://host.docker.internal:8010")


def _dsn() -> str:
    return os.getenv("DATABASE_URL", "postgresql://admin:secret@knowledge_postgres:5432/knowledge_os")


def map_category_to_expert(category: str) -> Optional[str]:
    c = (category or "").lower()
    for marker, expert in CATEGORY_TO_EXPERT:
        if marker in c:
            return expert
    return None


def _compose_override_text(meta: dict) -> Optional[str]:
    summary = str(meta.get("wisdom_summary") or meta.get("core_thesis") or "").strip()
    instruction = str(meta.get("instruction") or "").strip()
    if not summary and not instruction:
        return None
    parts = []
    if summary:
        parts.append(f"Урок из опыта (high-band wisdom): {summary[:500]}")
    if instruction:
        parts.append(f"Применяй: {instruction[:250]}")
    text = "\n".join(parts)
    return text[:MAX_WISDOM_DNA_CHARS] if len(text) > MAX_WISDOM_DNA_CHARS else text


async def select_wisdom_batch(limit: int = 30) -> List[Dict[str, Any]]:
    conn = await asyncpg.connect(_dsn())
    try:
        rows = await conn.fetch(
            """
            SELECT id, confidence_score,
                   metadata->>'category' AS category,
                   metadata->>'wisdom_summary' AS wisdom_summary,
                   metadata->>'instruction' AS instruction,
                   metadata->>'core_thesis' AS core_thesis
            FROM knowledge_nodes
            WHERE metadata->>'distilled' = 'true'
              AND metadata->>'distillation_quality_band' = 'high'
              AND confidence_score >= 0.8
              AND metadata->>'injected_into_dna' IS NULL
            ORDER BY confidence_score DESC, created_at DESC
            LIMIT $1
            """,
            limit,
        )
    finally:
        await conn.close()
    out = []
    for r in rows:
        expert = map_category_to_expert(r["category"])
        if not expert:
            continue
        text = _compose_override_text(
            {
                "wisdom_summary": r["wisdom_summary"],
                "instruction": r["instruction"],
                "core_thesis": r["core_thesis"],
            }
        )
        if not text:
            continue
        out.append(
            {
                "node_id": str(r["id"]),
                "expert": expert,
                "category": r["category"],
                "confidence": float(r["confidence_score"] or 0),
                "override_text": text,
            }
        )
    return out


async def run_answer(goal: str) -> str:
    """Ответ Виктории через боевой /run (async + poll)."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{VICTORIA_URL}/run?async_mode=true", json={"goal": goal})
        data = resp.json()
    if data.get("status") == "success" and data.get("output"):
        return str(data["output"])[:1500]
    task_id = data.get("task_id")
    if not task_id:
        return "[ERROR] no task_id"
    deadline = time.monotonic() + RUN_TIMEOUT
    while time.monotonic() < deadline:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                rec = await client.get(f"{VICTORIA_URL}/run/status/{task_id}")
            rec = rec.json()
            if rec.get("status") in ("completed", "failed"):
                out = str(rec.get("output") or "")
                return out[:1500] if out else f"[{rec.get('status')}] empty"
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(3)
    return "[ERROR] timeout"


async def eval_expert(expert: str, questions: List[str]) -> List[str]:
    """Ответы эксперта для eval.

    Виктория (дефолтный ответчик /run): боевой deep-путь «объясни …» → no-clarify.
    Специалисты: прямой вызов мозга (MLX wisdom) с ПОЛНЫМ промптом эксперта
    (get_full_expert_prompt включает wisdom_dna) — измеряет именно эффект урока,
    не завязан на слабые руки (phi3.5).
    """
    if expert == "Виктория":
        answers = []
        for q in questions:
            goal = f"объясни: {q}"
            try:
                answers.append(
                    await asyncio.wait_for(run_answer(goal), timeout=RUN_TIMEOUT + 120)
                )
            except Exception as e:  # noqa: BLE001
                answers.append(f"[ERROR] {e}"[:200])
        return answers

    # Чистый A/B: роль эксперта + (после инъекции) wisdom_dna.
    # Без шумных блоков полного промпта — измеряем ровно ценность урока.
    import asyncpg as _apg

    _conn = await _apg.connect(_dsn())
    try:
        _row = await _conn.fetchrow(
            "SELECT role, COALESCE(metadata,'{}'::jsonb) AS meta FROM experts WHERE name = $1",
            expert,
        )
    finally:
        await _conn.close()
    role = (_row["role"] if _row else "") or "эксперт"
    wisdom = ""
    if _row:
        _meta = _row["meta"]
        wisdom = str((_meta.get("wisdom_dna") if isinstance(_meta, dict) else "") or "")

    system_prompt = (
        f"Ты — {expert}, {role} корпорации ATRA. Отвечай по существу вопроса, "
        f"конкретно, на русском языке, без рассуждений о себе."
    )
    if wisdom:
        system_prompt += f"\n\nОпирайся на этот урок из опыта: {wisdom[:MAX_WISDOM_DNA_CHARS]}"
    mlx = (
        os.getenv("MLX_BASE_URL", "").rstrip("/")
        or os.getenv("MLX_API_URL", "").rstrip("/")
        or "http://host.docker.internal:11435"
    )
    model = os.getenv("VICTORIA_WISDOM_MODEL", "victoria-wisdom-24k")

    answers = []
    async with httpx.AsyncClient(timeout=300) as client:
        for q in questions:
            try:
                r = await client.post(
                    f"{mlx}/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": q},
                        ],
                        "stream": False,
                        "options": {"num_predict": 400},
                    },
                )
                raw = str(r.json().get("message", {}).get("content", ""))
                # [v148] Мозг начинает с <think> — стрипаем, иначе судье
                # после обрезки достаются только размышления.
                import re as _re

                raw = _re.sub(r"<think>.*?</think>", "", raw, flags=_re.DOTALL).strip()
                answers.append(raw[:1500])
            except Exception as e:  # noqa: BLE001
                answers.append(f"[ERROR] {e}"[:200])
    return answers


async def judge_pair(goal: str, answer_before: str, answer_after: str) -> Dict[str, Any]:
    mlx = os.getenv("MLX_BASE_URL", "").rstrip("/") or os.getenv("MLX_API_URL", "").rstrip("/") or "http://host.docker.internal:11435"
    model = os.getenv("VICTORIA_WISDOM_MODEL", "victoria-wisdom-24k")
    prompt = (
        "Ты — строгий судья. Эксперт-ассистент получил новый урок в инструкции (после). "
        "Оцени оба ответа на один вопрос 0-10: корректность, конкретность, полезность.\n\n"
        f"ВОПРОС: {goal}\n\nОТВЕТ ДО:\n{answer_before[:2000]}\n\n"
        f"ОТВЕТ ПОСЛЕ:\n{answer_after[:2000]}\n\n"
        'Ответь ТОЛЬКО JSON: {"before": <0-10>, "after": <0-10>, "winner": "before"|"after"|"tie", "reason": "<фраза>"}'
    )
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{mlx}/api/chat",
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False},
            )
        import re as _re

        raw = r.json().get("message", {}).get("content") or ""
        # [v148] Think может быть незакрытым — отрезаем всё до конца </think>.
        if "</think>" in raw:
            raw = raw.split("</think>", 1)[1]
        raw = raw.replace("<think>", "").strip()
        # Перебор всех "{" — первый валидный JSON-объект побеждает
        # (в размышлениях тоже встречаются "{...}").
        v = None
        for idx, ch in enumerate(raw):
            if ch != "{":
                continue
            try:
                v, _ = json.JSONDecoder().raw_decode(raw[idx:])
                break
            except json.JSONDecodeError:
                continue
        if v is not None:
            return {
                "before": float(v.get("before", 0)),
                "after": float(v.get("after", 0)),
                "winner": v.get("winner", "tie"),
                "reason": str(v.get("reason", ""))[:150],
            }
    except Exception as e:  # noqa: BLE001
        return {"before": 0.0, "after": 0.0, "winner": "error", "reason": str(e)[:120]}
    return {"before": 0.0, "after": 0.0, "winner": "error", "reason": "judge parse failed"}


async def inject_wisdom_dna(conn, expert: str, node_id: str, text: str) -> bool:
    """Записать wisdom в experts.metadata.wisdom_dna (+история), маркер на узле."""
    row = await conn.fetchrow(
        "SELECT id, auto_dna_sync, COALESCE(metadata,'{}'::jsonb) AS meta FROM experts WHERE name = $1",
        expert,
    )
    if not row or row["auto_dna_sync"] is False:
        logger.warning("[DNA-INJ] %s: не найден или auto_dna_sync=false — пропуск", expert)
        return False
    meta = dict(row["meta"]) if isinstance(row["meta"], dict) else json.loads(row["meta"] or "{}")
    prev = meta.get("wisdom_dna")
    history = meta.get("wisdom_dna_history") or []
    if prev:
        history.append({"text": prev, "at": datetime.now(timezone.utc).isoformat()})
    meta["wisdom_dna"] = text
    meta["wisdom_dna_history"] = history[-3:]
    await conn.execute(
        "UPDATE experts SET metadata = $2::jsonb, last_dna_sync = now() WHERE id = $1::uuid",
        row["id"],
        json.dumps(meta, ensure_ascii=False),
    )
    await conn.execute(
        """
        UPDATE knowledge_nodes
        SET metadata = COALESCE(metadata,'{}'::jsonb)
            || jsonb_build_object('injected_into_dna', true, 'injected_expert', $2::text, 'injected_at', now()::text)
        WHERE id = $1::uuid
        """,
        _uuid.UUID(node_id),
        expert,
    )
    return True


async def rollback_wisdom_dna(conn, expert: str, node_id: str) -> None:
    row = await conn.fetchrow(
        "SELECT id, COALESCE(metadata,'{}'::jsonb) AS meta FROM experts WHERE name = $1", expert
    )
    if not row:
        return
    meta = dict(row["meta"]) if isinstance(row["meta"], dict) else json.loads(row["meta"] or "{}")
    history = meta.get("wisdom_dna_history") or []
    meta["wisdom_dna"] = history.pop()["text"] if history else None
    meta["wisdom_dna_history"] = history
    await conn.execute(
        "UPDATE experts SET metadata = $2::jsonb WHERE id = $1::uuid",
        row["id"],
        json.dumps(meta, ensure_ascii=False),
    )
    await conn.execute(
        """
        UPDATE knowledge_nodes
        SET metadata = COALESCE(metadata,'{}'::jsonb) || '{"injected_into_dna":"rollback"}'::jsonb
        WHERE id = $1::uuid
        """,
        _uuid.UUID(node_id),
    )


async def run_injection_cycle(dry_run: bool = False) -> Dict[str, Any]:
    if os.getenv("DNA_INJECTION_ENABLED", "true").lower() not in ("1", "true", "yes"):
        return {"status": "disabled"}
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report: Dict[str, Any] = {"timestamp": ts, "dry_run": dry_run, "injections": [], "skipped": 0}

    batch = await select_wisdom_batch(limit=30)
    # Фильтр разрешённых экспертов: пока eval-инфраструктура специалистов флапает
    # (in-process), надёжен только /run-путь Виктории. Расширение — конфигом:
    # DNA_INJECTION_ALLOWED_EXPERTS="Виктория,Анна,Игорь".
    allowed_raw = os.getenv("DNA_INJECTION_ALLOWED_EXPERTS", "Виктория")
    allowed = {x.strip() for x in allowed_raw.split(",") if x.strip()}
    batch = [b for b in batch if b["expert"] in allowed]
    by_expert: Dict[str, List[Dict]] = {}
    for w in batch:
        by_expert.setdefault(w["expert"], [])
        if len(by_expert[w["expert"]]) < 1:
            by_expert[w["expert"]].append(w)
    chosen: List[Dict] = []
    for expert, items in list(by_expert.items())[:MAX_EXPERTS_PER_CYCLE]:
        chosen.extend(items[:1])

    for w in chosen:
        expert = w["expert"]
        questions = (EXPERT_EVAL_QUESTIONS.get(expert) or [])[:EVAL_QUESTIONS]
        if not questions:
            report["skipped"] += 1
            continue
        entry = {**w, "questions": questions}
        if dry_run:
            entry["action"] = "dry_run"
            report["injections"].append(entry)
            continue
        conn = await asyncpg.connect(_dsn())
        try:
            before = await eval_expert(expert, questions)
            # Не инъектировать при уже сломанном before — не тратить узлы.
            if any(a.startswith("[ERROR]") for a in before):
                entry.update(
                    {
                        "action": "skipped_before_errors",
                        "verdict": {"reason": "before-ответы с ошибками (инфраструктура)"},
                    }
                )
                logger.error("🚨 [DNA-INJ] %s: before-ошибки — цикл прерван без инъекции", expert)
                report["injections"].append(entry)
                continue
            ok = await inject_wisdom_dna(conn, expert, w["node_id"], w["override_text"])
            if not ok:
                entry["action"] = "skipped_auto_dna_sync"
                report["injections"].append(entry)
                continue
            after = await eval_expert(expert, questions)
            bad = [a for a in (before + after) if a.startswith("[ERROR]")]
            if bad:
                await rollback_wisdom_dna(conn, expert, w["node_id"])
                entry.update(
                    {
                        "action": "rolled_back_eval_errors",
                        "verdict": {"reason": f"{len(bad)} eval-вызовов с ошибками"},
                    }
                )
                logger.error("🚨 [DNA-INJ] %s: eval-ошибки — откат", expert)
            else:
                verdict = await judge_pair(questions[0], before[0], after[0])
                if verdict["winner"] == "error":
                    await rollback_wisdom_dna(conn, expert, w["node_id"])
                    entry.update({"action": "rolled_back_judge_error", "verdict": verdict})
                    logger.error("🚨 [DNA-INJ] %s: ошибка судьи — откат", expert)
                # Гейт качества: 0-балльные ответы = пустышки — подтверждать пользу нечем.
                elif verdict["before"] <= 0 or verdict["after"] <= 0:
                    await rollback_wisdom_dna(conn, expert, w["node_id"])
                    entry.update({"action": "rolled_back_empty_answers", "verdict": verdict})
                    logger.error("🚨 [DNA-INJ] %s: пустые ответы — откат", expert)
                elif verdict["winner"] == "after" or (
                    verdict["winner"] == "tie" and verdict["after"] >= verdict["before"]
                ):
                    entry.update({"action": "kept", "verdict": verdict})
                elif verdict["winner"] == "error":
                    await rollback_wisdom_dna(conn, expert, w["node_id"])
                    entry.update({"action": "rolled_back_judge_error", "verdict": verdict})
                else:
                    await rollback_wisdom_dna(conn, expert, w["node_id"])
                    entry.update({"action": "rolled_back_degradation", "verdict": verdict})
                    logger.error(
                        "🚨 [DNA-INJ] %s: деградация — откат (%s)", expert, verdict["reason"]
                    )
            report["injections"].append(entry)
        finally:
            await conn.close()

    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "backups", "dna_reports"
    )
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"dna_injection_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1, default=str)
    logger.info(
        "🧬 [DNA-INJ] cycle done: %d injections, %d skipped → %s",
        len(report["injections"]),
        report["skipped"],
        out_path,
    )
    report["report_path"] = out_path
    return report


async def run_continuous_dna_injection() -> None:
    interval = int(os.getenv("DNA_INJECTION_INTERVAL_SEC", "21600"))
    while True:
        try:
            await run_injection_cycle(dry_run=False)
        except Exception as e:  # noqa: BLE001
            logger.error("🧬 [DNA-INJ] cycle failed: %s", e)
        await asyncio.sleep(interval)


if __name__ == "__main__":
    import sys

    asyncio.run(run_injection_cycle(dry_run="--dry-run" in sys.argv))
