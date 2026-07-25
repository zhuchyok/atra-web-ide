"""
Nightly Expert Council (Red Team) — restored after Phase 8.2 cleanup regression.

Writes knowledge_nodes with metadata.cycle = nightly_council_v2 for Wisdom tab,
updates source node council_review, and persists expert_discussions when possible.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)

COUNCIL_MODEL = os.getenv("NIGHTLY_COUNCIL_MODEL", "phi3.5:3.8b")
COUNCIL_ROUND_TIMEOUT_SEC = float(os.getenv("NIGHTLY_COUNCIL_ROUND_TIMEOUT_SEC", "60"))
COUNCIL_PHASE_LIMIT = int(os.getenv("NIGHTLY_COUNCIL_PHASE_LIMIT", "2"))
COUNCIL_MIN_CONFIDENCE = float(os.getenv("NIGHTLY_COUNCIL_MIN_CONFIDENCE", "0.85"))


async def _llm(prompt: str) -> str:
    try:
        from dialogue_llm import generate_dialogue_text

        text = await asyncio.wait_for(
            generate_dialogue_text(prompt, expert_name="Виктория", model_hint=COUNCIL_MODEL),
            timeout=COUNCIL_ROUND_TIMEOUT_SEC,
        )
        return (text or "").strip()
    except Exception as exc:
        logger.warning("council LLM failed: %s", exc)
        return ""


def _parse_consensus_score(text: str) -> float | None:
    if not text:
        return None
    patterns = [
        r"(?:confidence|уверенност\w*|score|консенсус)[^\d]{0,20}(0?\.\d+|1\.0)",
        r"\b(0\.\d{1,2}|1\.0)\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if not m:
            continue
        try:
            val = float(m.group(1))
            if 0.0 < val <= 1.0:
                return val
        except ValueError:
            continue
    return None


def _as_uuid(value: Any) -> Any:
    if isinstance(value, UUID):
        return value
    return value


async def run_expert_council(
    conn: asyncpg.Connection,
    knowledge_id: Any,
    content: str,
    original_expert_id: Any,
) -> str | None:
    """
    Red Team debate (critique → rebuttal → synthesis).
    Returns id of the council knowledge_node when created.
    """
    knowledge_id = _as_uuid(knowledge_id)
    original_expert_id = _as_uuid(original_expert_id)
    snippet = (content or "").strip()[:1200]
    if not snippet:
        logger.warning("council skip: empty content for %s", knowledge_id)
        return None

    logger.info("🏛️ [COUNCIL] Starting for knowledge_id=%s", knowledge_id)
    author = await conn.fetchrow(
        "SELECT id, name, role FROM experts WHERE id = $1", original_expert_id
    )
    opponents = await conn.fetch(
        """
        SELECT id, name, role
        FROM experts
        WHERE id != $1
        ORDER BY RANDOM()
        LIMIT 2
        """,
        original_expert_id,
    )
    if not author or not opponents:
        logger.warning("council skip: missing author/opponents")
        return None

    debate_log: list[str] = [f"📝 **Автор ({author['name']}):** {snippet[:500]}"]
    criticisms: list[str] = []

    # Round 1 — critique
    for opp in opponents:
        prompt = f"""Ты RED TEAM эксперт {opp["name"]} ({opp["role"]}).
Найди 2-3 критических риска/ошибки в инсайте (кратко, 2-3 предложения):
\"{snippet}\"
Ответь только критикой, без вступлений."""
        comment = await _llm(prompt)
        if not comment:
            comment = (
                f"Риск: инсайт «{snippet[:80]}» недостаточно операционализирован "
                f"(нет метрик успеха и rollback)."
            )
        criticisms.append(f"🧐 {opp['name']} ({opp['role']}): {comment}")
        debate_log.append(f"❌ **Критика от {opp['name']}:** {comment}")

    # Round 2 — author rebuttal
    rebuttal_prompt = f"""Ты {author["name"]} ({author["role"]}).
Твой инсайт: \"{snippet}\"
Критика:
{chr(10).join(criticisms)}

Ответь кратко (2-3 предложения): признай слабые места или защити позицию."""
    rebuttal = await _llm(rebuttal_prompt) or (
        "Часть критики справедлива: добавим измеримые критерии и проверку health до внедрения."
    )
    debate_log.append(f"🛡️ **Ответ автора ({author['name']}):** {rebuttal}")

    # Round 3 — synthesis
    synthesis_prompt = f"""Ты нейтральный арбитр корпорации ATRA.
Ход обсуждения:
{chr(10).join(debate_log)}

Сформулируй итоговый консенсус (4-6 предложений) и укажи confidence 0.0-1.0 явно числом."""
    consensus = await _llm(synthesis_prompt)
    if not consensus:
        consensus = (
            f"Консенсус (fallback): инсайт полезен как гипотеза, но требует пилота. "
            f"Confidence: 0.72. Автор: {author['name']}; оппоненты: "
            + ", ".join(o["name"] for o in opponents)
        )
    score = _parse_consensus_score(consensus)
    if score is None:
        score = 0.72

    full_summary = "\n\n".join(debate_log) + f"\n\n🏁 **ИТОГОВЫЙ КОНСЕНСУС:**\n{consensus}"

    # Persist discussion row (best-effort)
    try:
        await conn.execute(
            """
            INSERT INTO expert_discussions
                (knowledge_node_id, expert_ids, topic, consensus_summary, status, metadata)
            VALUES ($1, $2, $3, $4, 'closed', $5::jsonb)
            """,
            knowledge_id,
            [original_expert_id] + [o["id"] for o in opponents],
            snippet[:100],
            full_summary[:20000],
            json.dumps(
                {
                    "cycle": "nightly_council_v2",
                    "consensus_score": score,
                    "author": author["name"],
                },
                ensure_ascii=False,
            ),
        )
    except Exception as exc:
        logger.warning("expert_discussions insert failed: %s", exc)

    # Mark source node reviewed
    try:
        await conn.execute(
            """
            UPDATE knowledge_nodes
            SET metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                'council_review', $1::text,
                'red_team_status', 'passed',
                'consensus_score', to_jsonb($2::float)
            ),
            updated_at = NOW()
            WHERE id = $3
            """,
            consensus[:4000],
            score,
            knowledge_id,
        )
    except Exception as exc:
        logger.warning("source node council_review update failed: %s", exc)

    # Wisdom-tab visible node
    domain_id = await conn.fetchval(
        "SELECT domain_id FROM knowledge_nodes WHERE id = $1", knowledge_id
    )
    if domain_id is None:
        domain_id = await conn.fetchval(
            "SELECT id FROM domains WHERE name IN ('Wisdom & Heuristics', 'Mentorship') ORDER BY name LIMIT 1"
        )
    if domain_id is None:
        domain_id = await conn.fetchval(
            "INSERT INTO domains (name) VALUES ('Wisdom & Heuristics') RETURNING id"
        )

    council_content = (
        f"🏛️ Expert Council Debate\n"
        f"Source: {knowledge_id}\n"
        f"Author: {author['name']}\n\n"
        f"{full_summary}"
    )
    meta = {
        "cycle": "nightly_council_v2",
        "type": "expert_council_debate",
        "source_knowledge_id": str(knowledge_id),
        "consensus_score": score,
        "author": author["name"],
        "opponents": [o["name"] for o in opponents],
    }
    content_to_store = council_content[:50000]
    emb_str = None
    try:
        from embedding_eligibility import get_embedding_vector_str

        emb_str = await get_embedding_vector_str(content_to_store)
    except Exception:
        emb_str = None

    if emb_str:
        council_node_id = await conn.fetchval(
            """
            INSERT INTO knowledge_nodes
                (domain_id, content, confidence_score, metadata, is_verified, embedding)
            VALUES ($1, $2, $3, $4::jsonb, true, $5::vector)
            RETURNING id
            """,
            domain_id,
            content_to_store,
            score,
            json.dumps(meta, ensure_ascii=False),
            emb_str,
        )
    else:
        council_node_id = await conn.fetchval(
            """
            INSERT INTO knowledge_nodes
                (domain_id, content, confidence_score, metadata, is_verified)
            VALUES ($1, $2, $3, $4::jsonb, true)
            RETURNING id
            """,
            domain_id,
            content_to_store,
            score,
            json.dumps(meta, ensure_ascii=False),
        )
    logger.info(
        "✅ [COUNCIL] Finished node=%s score=%.2f source=%s",
        council_node_id,
        score,
        knowledge_id,
    )
    return str(council_node_id) if council_node_id else None


async def run_nightly_council_phase(limit: int | None = None) -> int:
    """Pick recent high-confidence nodes without council_review and debate them."""
    lim = max(1, limit if limit is not None else COUNCIL_PHASE_LIMIT)
    db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DIRECT_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL (or POSTGRES_DIRECT_URL) is required for council phase")
    conn = await asyncpg.connect(db_url)
    created = 0
    try:
        rows = await conn.fetch(
            """
            SELECT kn.id, kn.content, kn.domain_id,
                   COALESCE(kn.metadata->>'expert', kn.metadata->>'author') AS expert_name
            FROM knowledge_nodes kn
            WHERE kn.confidence_score >= $1
              AND (kn.metadata->>'council_review' IS NULL
                   OR kn.metadata->>'council_review' = ''
                   OR kn.metadata->>'council_review' = 'null')
              AND COALESCE(kn.metadata->>'cycle', '') NOT LIKE 'nightly_council%'
              AND kn.created_at > NOW() - INTERVAL '60 days'
              AND LENGTH(COALESCE(kn.content, '')) > 80
            ORDER BY kn.confidence_score DESC, kn.created_at DESC
            LIMIT $2
            """,
            COUNCIL_MIN_CONFIDENCE,
            lim,
        )
        if not rows:
            logger.info("[COUNCIL] No eligible nodes for nightly phase")
            return 0

        for row in rows:
            expert = None
            if row["expert_name"]:
                expert = await conn.fetchrow(
                    "SELECT id FROM experts WHERE name = $1 LIMIT 1", row["expert_name"]
                )
            if not expert:
                expert = await conn.fetchrow("SELECT id FROM experts ORDER BY RANDOM() LIMIT 1")
            if not expert:
                continue
            try:
                node_id = await run_expert_council(
                    conn, row["id"], row["content"] or "", expert["id"]
                )
                if node_id:
                    created += 1
            except Exception as exc:
                logger.error("council phase item failed %s: %s", row["id"], exc)
        logger.info("[COUNCIL] Nightly phase created %s debate node(s)", created)
        return created
    finally:
        await conn.close()
