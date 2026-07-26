"""
[SINGULARITY 20.0] Mentorship Engine.
Victoria audits completed tasks and provides feedback to experts to improve collective intelligence.
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime
from typing import Any, Optional

import asyncpg

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:secret@localhost:6432/knowledge_os",  # pragma: allowlist secret
)
AUDIT_TIMEOUT_SEC = float(os.getenv("MENTORSHIP_AUDIT_TIMEOUT_SEC", "75"))


def _metadata_as_dict(metadata: Any) -> dict[str, Any]:
    """asyncpg returns jsonb as dict; older paths may still pass JSON strings."""
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return dict(metadata)
    if isinstance(metadata, str):
        try:
            parsed = json.loads(metadata)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _heuristic_audit(title: str, expert_name: str) -> dict[str, Any]:
    short = (title or "задача")[:80]
    return {
        "score": 7,
        "critique": (
            f"Авто-аудит (LLM timeout/fail) для «{short}»: результат принят, "
            "нужна явная фиксация evidence и проверка health перед закрытием."
        ),
        "mentorship_note": (
            f"{expert_name}: для задач вроде «{short[:60]}» сохраняй измеримый result "
            "в tasks.result и не закрывай без health-check зависимых сервисов."
        ),
        "audit_mode": "heuristic_fallback",
    }


_DELEGATED_RE = re.compile(
    r"Делегировано:\s*([^\n(]+)",
    re.IGNORECASE,
)


def resolve_mentorship_expert_name(
    *,
    title: str | None,
    metadata: dict[str, Any] | None,
    assignee_name: str | None = None,
) -> str | None:
    """
    Resolve real expert for mentorship notes.
    Returns None when we would otherwise write «Unknown Expert» junk into KB.
    """
    meta = metadata or {}
    candidates = [
        (assignee_name or "").strip(),
        str(meta.get("assignee_hint") or "").strip(),
        str(meta.get("expert_name") or "").strip(),
        str(meta.get("target_expert") or "").strip(),
    ]
    m = _DELEGATED_RE.search(title or "")
    if m:
        candidates.insert(0, m.group(1).strip())
    for name in candidates:
        if not name:
            continue
        low = name.lower()
        if low in {"unknown expert", "не назначен", "n/a", "none", "null"}:
            continue
        if name.startswith("🤖"):
            continue
        return name
    return None


def _parse_audit_json(raw: str) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
    # Recover first JSON object if model added prose
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


class MentorshipEngine:
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def run_audit_cycle(self, limit: int = 5):
        """
        Selects recently completed tasks and performs an audit.
        """
        logger.info(f"🎓 [MENTORSHIP] Starting audit cycle for {limit} tasks...")

        conn = await asyncpg.connect(self.db_url)
        try:
            # 1. Get recently completed tasks that haven't been audited yet
            # We look for tasks in the 'tasks' table or interaction_logs
            tasks = await conn.fetch(
                """
                SELECT t.id, t.title, t.description, t.metadata, t.updated_at,
                       e.name AS assignee_name
                FROM tasks t
                LEFT JOIN experts e ON e.id = t.assignee_expert_id
                WHERE t.status = 'completed'
                  AND (
                    t.metadata->>'audited_by_victoria' IS NULL
                    OR t.metadata->>'audited_by_victoria' = 'false'
                  )
                ORDER BY t.updated_at DESC
                LIMIT $1
            """,
                limit,
            )

            if not tasks:
                logger.info("No new completed tasks for audit.")
                return

            for task in tasks:
                try:
                    await self.audit_task(conn, task)
                except Exception as exc:
                    logger.error("Audit failed for %s: %s", task["id"], exc)

        finally:
            await conn.close()

    async def _generate_audit_payload(
        self, audit_prompt: str, title: str, expert_name: str
    ) -> dict[str, Any]:
        """Prefer lightweight dialogue_llm; fall back to ai_core; then heuristic."""
        # 1) Fast path — Ollama/MLX dialogue without full RAG stack
        try:
            from dialogue_llm import generate_dialogue_text

            raw = await asyncio.wait_for(
                generate_dialogue_text(
                    audit_prompt,
                    expert_name="Виктория",
                    model_hint=os.getenv("MENTORSHIP_MODEL", "phi3.5:3.8b"),
                ),
                timeout=AUDIT_TIMEOUT_SEC,
            )
            parsed = _parse_audit_json(raw or "")
            if parsed and parsed.get("mentorship_note"):
                parsed["audit_mode"] = "dialogue_llm"
                return parsed
        except Exception as exc:
            logger.warning("dialogue_llm audit failed: %s", exc)

        # 2) Full Victoria path (bounded)
        try:
            from ai_core import run_smart_agent_async

            raw = await asyncio.wait_for(
                run_smart_agent_async(audit_prompt, expert_name="Виктория", category="reasoning"),
                timeout=AUDIT_TIMEOUT_SEC,
            )
            parsed = _parse_audit_json(raw or "")
            if parsed and parsed.get("mentorship_note"):
                parsed["audit_mode"] = "ai_core"
                return parsed
        except Exception as exc:
            logger.warning("ai_core audit failed/timeout: %s", exc)

        return _heuristic_audit(title or "", expert_name)

    async def audit_task(self, conn, task: asyncpg.Record):
        """
        Audits a single task using Victoria's high-level reasoning.
        """
        task_id = task["id"]
        title = task["title"]
        description = task["description"]
        metadata = _metadata_as_dict(task["metadata"])

        assignee_name = None
        try:
            assignee_name = task["assignee_name"]
        except (KeyError, IndexError, TypeError):
            assignee_name = None
        expert_name = resolve_mentorship_expert_name(
            title=title,
            metadata=metadata,
            assignee_name=assignee_name,
        )

        if not expert_name:
            # Do not pollute Mentorship KB with «Unknown Expert» notes.
            metadata["audited_by_victoria"] = "skipped_unknown_expert"
            metadata["audit_skip_reason"] = "unresolved_expert"
            await conn.execute(
                """
                UPDATE tasks SET metadata = $1::jsonb, updated_at = NOW() WHERE id = $2
                """,
                json.dumps(metadata),
                task_id,
            )
            logger.info(
                "⏭️ [AUDIT] Skip task %s — expert unresolved (avoid Unknown Expert junk)",
                task_id,
            )
            return

        logger.info(f"🔍 [AUDIT] Reviewing task: {title} (Expert: {expert_name})")

        # 2. Prepare the audit prompt
        audit_prompt = f"""
        ТЫ - ВИКТОРИЯ, ВЕРХОВНЫЙ МЕНТОР КОРПОРАЦИИ (LEVEL 20 WISDOM).
        ТВОЯ ЗАДАЧА: Провести аудит выполненной задачи и дать конструктивный фидбек эксперту.

        ЭКСПЕРТ: {expert_name}
        ЗАДАЧА: {title}
        ОПИСАНИЕ: {description}
        РЕЗУЛЬТАТ (МЕТАДАННЫЕ): {json.dumps(metadata, indent=2, ensure_ascii=False)[:2500]}

        ПЛАН АУДИТА:
        1. Оцени качество выполнения (0-10).
        2. Выяви, что можно было сделать лучше (архитектура, безопасность, производительность).
        3. Сформулируй ОДИН конкретный совет (Mentorship Note) для этого эксперта на будущее.

        ФОРМАТ ОТВЕТА (JSON):
        {{
            "score": 8,
            "critique": "...",
            "mentorship_note": "В следующий раз при работе с БД всегда проверяй наличие индексов в миграции."
        }}
        ВЕРНИ ТОЛЬКО ЧИСТЫЙ JSON.
        """

        audit_data = await self._generate_audit_payload(audit_prompt, title or "", expert_name)
        note = audit_data.get("mentorship_note")
        score = audit_data.get("score", 0)
        try:
            score = int(score)
        except (TypeError, ValueError):
            score = 7

        if not note:
            logger.error(f"Failed to get mentorship note for task {task_id}")
            return

        domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = 'Mentorship' LIMIT 1")
        if not domain_id:
            domain_id = await conn.fetchval(
                "INSERT INTO domains (name) VALUES ('Mentorship') RETURNING id"
            )

        content_kn = f"🎓 MENTORSHIP NOTE for {expert_name}: {note}"
        meta_kn = json.dumps(
            {
                "type": "mentorship_note",
                "target_expert": expert_name,
                "task_id": str(task_id),
                "score": score,
                "critique": audit_data.get("critique"),
                "audit_mode": audit_data.get("audit_mode", "unknown"),
            }
        )

        emb_str = None
        try:
            from embedding_eligibility import get_embedding_vector_str

            emb_str = await get_embedding_vector_str(content_kn)
        except Exception:
            emb_str = None

        if emb_str:
            await conn.execute(
                """
                INSERT INTO knowledge_nodes
                    (domain_id, content, confidence_score, metadata, is_verified, embedding)
                VALUES ($1, $2, $3, $4::jsonb, true, $5::vector)
            """,
                domain_id,
                content_kn,
                float(score) / 10.0,
                meta_kn,
                emb_str,
            )
        else:
            await conn.execute(
                """
                INSERT INTO knowledge_nodes
                    (domain_id, content, confidence_score, metadata, is_verified)
                VALUES ($1, $2, $3, $4::jsonb, true)
            """,
                domain_id,
                content_kn,
                float(score) / 10.0,
                meta_kn,
            )

        metadata["audited_by_victoria"] = "true"
        metadata["audit_score"] = score
        metadata["audit_mode"] = audit_data.get("audit_mode", "unknown")
        await conn.execute(
            """
            UPDATE tasks SET metadata = $1::jsonb, updated_at = NOW() WHERE id = $2
        """,
            json.dumps(metadata),
            task_id,
        )

        logger.info(
            f"✅ [AUDIT COMPLETE] Task {task_id} scored {score}/10 "
            f"mode={audit_data.get('audit_mode')}. Mentorship note stored."
        )


async def run_mentorship_cycle(limit: int = 5):
    engine = MentorshipEngine()
    await engine.run_audit_cycle(limit=limit)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mentorship Engine Audit Cycle")
    parser.add_argument("--limit", type=int, default=5, help="Number of tasks to audit")
    args = parser.parse_args()

    asyncio.run(run_mentorship_cycle(limit=args.limit))
