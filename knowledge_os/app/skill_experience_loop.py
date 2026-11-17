"""
KISS closed skill/experience loop for experts (Hermes-pattern borrow).

Stores lessons in knowledge_nodes (kind=experience). Does NOT mutate SKILL.md.
Shared helpers so expert_worker never imports victoria_server.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

_DEFAULT_DSN = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


def is_skill_loop_enabled(default: bool = True) -> bool:
    raw = os.getenv("SKILL_LOOP_ENABLED")
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def format_lessons_block(lessons: List[str]) -> str:
    cleaned = [str(x).strip() for x in (lessons or []) if str(x).strip()]
    if not cleaned:
        return ""
    lines = ["### EXPERIENCE LESSONS (past):"]
    for i, lesson in enumerate(cleaned, 1):
        lines.append(f"{i}. {lesson[:300]}")
    return "\n".join(lines)


def append_experience_lessons(description: str, lessons: List[str]) -> str:
    block = format_lessons_block(lessons)
    if not block:
        return description
    return f"{block}\n\n{description}"


async def fetch_experience_lessons(
    goal_text: str, limit: int = 3, *, dsn: Optional[str] = None
) -> List[str]:
    """Top-N relevant experience rows from knowledge_nodes (kind=experience)."""
    goal = (goal_text or "").strip()
    if not goal or limit <= 0:
        return []
    try:
        conn = await asyncpg.connect(dsn=dsn or _DEFAULT_DSN)
        try:
            # content_tsvector is filled by trigger to_tsvector('russian', ...);
            # 'simple' query config never matches stemmed EN tokens → always
            # fell through to newest-only fallback (skill-loop value loss).
            rows = await conn.fetch(
                """SELECT content FROM knowledge_nodes
                   WHERE metadata @> '{"kind":"experience"}'::jsonb
                     AND content_tsvector @@ plainto_tsquery('russian', $1)
                   ORDER BY ts_rank(content_tsvector, plainto_tsquery('russian', $1)) DESC,
                            created_at DESC
                   LIMIT $2""",
                goal[:400],
                limit,
            )
            if not rows:
                rows = await conn.fetch(
                    """SELECT content FROM knowledge_nodes
                       WHERE metadata @> '{"kind":"experience"}'::jsonb
                       ORDER BY created_at DESC LIMIT $1""",
                    limit,
                )
        finally:
            await conn.close()
        return [str(r["content"])[:300] for r in rows]
    except Exception as e:  # noqa: BLE001
        logger.debug("experience fetch failed: %s", e)
        return []


async def commit_experience_lesson(
    *,
    goal: str,
    outcome: str,
    lesson: str,
    source: str = "expert_worker",
    expert_name: str = "",
    dsn: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert compact experience node; sha1 dedup on goal+outcome (30d window)."""
    goal = (goal or "").strip()
    lesson = (lesson or "").strip()
    outcome = (outcome or "partial").strip() or "partial"
    source = (source or "expert_worker").strip()
    if not goal or not lesson:
        return {"status": "error", "detail": "goal and lesson required"}

    dedup_key = hashlib.sha1(f"{goal[:200]}|{outcome}".encode()).hexdigest()
    metadata = {
        "kind": "experience",
        "dedup": dedup_key,
        "outcome": outcome,
        "source": source,
        "created_by": "skill-experience-loop",
    }
    if expert_name:
        metadata["expert_name"] = expert_name

    try:
        conn = await asyncpg.connect(dsn=dsn or _DEFAULT_DSN)
        try:
            row = await conn.fetchrow(
                """SELECT id FROM knowledge_nodes
                   WHERE metadata @> $1::jsonb AND created_at > NOW() - INTERVAL '30 days'
                   LIMIT 1""",
                json.dumps({"dedup": dedup_key}),
            )
            if row:
                return {"status": "duplicate", "node_id": str(row["id"]), "dedup": dedup_key}
            node_id = await conn.fetchval(
                """INSERT INTO knowledge_nodes
                   (content, metadata, confidence_score, source_ref)
                   VALUES ($1, $2::jsonb, $3, $4) RETURNING id""",
                f"[experience:{outcome}] {goal[:300]} => {lesson[:800]}",
                json.dumps(metadata, ensure_ascii=False),
                0.55,
                source[:256],
            )
        finally:
            await conn.close()
        logger.info("🧠 [SKILL-LOOP] committed %s outcome=%s", str(node_id)[:8], outcome)
        return {"status": "ok", "node_id": str(node_id), "dedup": dedup_key}
    except Exception as e:  # noqa: BLE001
        logger.warning("commit_experience_lesson failed: %s", e)
        return {"status": "error", "detail": str(e)[:200]}


async def maybe_commit_expert_experience(
    *,
    goal: str,
    result: str,
    expert_name: str = "",
    outcome: str = "passed",
) -> Optional[Dict[str, Any]]:
    """WRITE path: gated by SKILL_LOOP_ENABLED (default true)."""
    if not is_skill_loop_enabled(default=True):
        return None
    goal = (goal or "").strip()
    result_head = (result or "").strip()[:400]
    if not goal or not result_head:
        return None
    lesson = result_head
    if expert_name:
        lesson = f"[{expert_name}] {result_head}"
    source = f"expert_worker:{expert_name}" if expert_name else "expert_worker"
    return await commit_experience_lesson(
        goal=goal[:300],
        outcome=outcome,
        lesson=lesson,
        source=source,
        expert_name=expert_name or "",
    )
