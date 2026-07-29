"""
RAG embedding eligibility (Singularity 31.2 / quality-over-quantity).

World practice: do not chase 100% vectors on operational junk.
Index high-value knowledge; exclude venv, audits, discovery stubs.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# metadata.type values that must not enter the vector index
NON_RAG_TYPES = (
    "success_retrieval_audit",
    "swarm_resolution",
    "recovery_incident",
    "mutation_rollout_report",
    "recruitment_event",
    "ollama_model",
    "database_optimization",
)

# Priority for backfill (lower = sooner)
PRIORITY_TYPES = (
    "mentorship_note",
    "sop_document",
    "expert_council_debate",
    "board_directive",
    "board_consult",
    "distilled_wisdom",
    "long_term_memory",
    "meta_wisdom",
    "research_kb",
    "neural_mutation",
)

# SQL fragment: node is worth embedding / counting in "eligible coverage"
ELIGIBLE_WHERE = """
    content IS NOT NULL
    AND length(trim(content)) >= 40
    AND COALESCE(metadata->>'type', '') NOT IN (
        'success_retrieval_audit',
        'swarm_resolution',
        'recovery_incident',
        'mutation_rollout_report',
        'recruitment_event',
        'ollama_model',
        'database_optimization'
    )
    AND content NOT LIKE 'PROJECT_FILE:%/venv/%'
    AND content NOT LIKE '%/site-packages/%'
    AND content NOT LIKE '💎 ФУНДАМЕНТАЛЬНОЕ ЗНАНИЕ: 📋 Discovery фаза%'
    AND content NOT LIKE '💎 ФУНДАМЕНТАЛЬНОЕ ЗНАНИЕ: ⚠️ Все источники недоступны%'
"""

BACKFILL_ORDER_BY = """
    CASE COALESCE(metadata->>'type', '')
        WHEN 'mentorship_note' THEN 1
        WHEN 'sop_document' THEN 2
        WHEN 'expert_council_debate' THEN 3
        WHEN 'board_directive' THEN 4
        WHEN 'board_consult' THEN 5
        WHEN 'distilled_wisdom' THEN 6
        WHEN 'long_term_memory' THEN 7
        WHEN 'meta_wisdom' THEN 8
        WHEN 'research_kb' THEN 9
        WHEN 'neural_mutation' THEN 10
        ELSE 50
    END ASC,
    COALESCE(confidence_score, 0) DESC,
    created_at DESC NULLS LAST
"""

# Path segments that must never be indexed into knowledge_nodes
SKIP_PATH_PARTS = (
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "site-packages",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    "eggs",
    ".eggs",
)


def path_is_indexable(path: str) -> bool:
    """Return False for venv/site-packages and other junk paths."""
    if not path:
        return False
    norm = path.replace("\\", "/").lower()
    parts = set(norm.split("/"))
    for skip in SKIP_PATH_PARTS:
        if skip.lower() in parts or f"/{skip.lower()}/" in f"/{norm}/":
            return False
    return True


def content_is_rag_eligible(content: str, metadata_type: str | None = None) -> bool:
    """Python-side mirror of ELIGIBLE_WHERE for writers/guards."""
    text = (content or "").strip()
    if len(text) < 40:
        return False
    mtype = (metadata_type or "").strip()
    if mtype in NON_RAG_TYPES:
        return False
    low = text.lower()
    if "project_file:" in low and ("/venv/" in low or "\\venv\\" in low):
        return False
    if "/site-packages/" in low or "\\site-packages\\" in low:
        return False
    if text.startswith("💎 ФУНДАМЕНТАЛЬНОЕ ЗНАНИЕ: 📋 Discovery фаза"):
        return False
    if text.startswith("💎 ФУНДАМЕНТАЛЬНОЕ ЗНАНИЕ: ⚠️ Все источники недоступны"):
        return False
    return True


async def get_embedding_vector_str(text: str) -> str | None:
    """Best-effort embedding for INSERT; returns pgvector literal or None."""
    clipped = (text or "").strip()[:8000]
    if not clipped:
        return None
    try:
        try:
            from semantic_cache import get_embedding
        except ImportError:
            from app.semantic_cache import get_embedding

        emb = await get_embedding(clipped)
        if emb is None:
            return None
        if isinstance(emb, list):
            return "[" + ",".join(map(str, emb)) + "]"
        return str(emb)
    except Exception as e:
        logger.debug("get_embedding_vector_str failed: %s", e)
        return None


async def backfill_eligible_embeddings(limit: int = 50) -> dict[str, Any]:
    """
    Fill embeddings for eligible nodes missing vectors (priority order).
    Safe for nightly/continuous: bounded limit, skips junk.
    v132: prefer local batch encode (cached ST) for catch-up throughput.
    """
    import asyncpg

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://admin:secret@localhost:6432/knowledge_os",  # pragma: allowlist secret
    )
    # Catch-up runs may request up to 2000; continuous nightly stays env-capped.
    limit = max(1, min(int(limit), 2000))
    updated = 0
    failed = 0
    conn = await asyncpg.connect(db_url)
    try:
        rows = await conn.fetch(
            f"""
            SELECT id, content
            FROM knowledge_nodes
            WHERE embedding IS NULL
              AND ({ELIGIBLE_WHERE})
            ORDER BY {BACKFILL_ORDER_BY}
            LIMIT $1
            """,
            limit,
        )
        if not rows:
            return {"updated": 0, "failed": 0, "candidates": 0}

        # Chunked encode→write (Ollama GPU preferred, ST singleton fallback).
        try:
            try:
                from semantic_cache import encode_texts_best
            except ImportError:
                from app.semantic_cache import encode_texts_best

            chunk = max(8, min(int(os.getenv("EMBED_BACKFILL_ENCODE_CHUNK", "64")), 128))
            for i in range(0, len(rows), chunk):
                batch_rows = rows[i : i + chunk]
                batch_texts = [(r["content"] or "").strip()[:8000] for r in batch_rows]
                try:
                    batch_vecs = await encode_texts_best(batch_texts)
                except Exception as exc:
                    logger.warning("chunk encode failed at %s: %s", i, exc)
                    batch_vecs = [None] * len(batch_rows)
                for row, vec in zip(batch_rows, batch_vecs):
                    try:
                        if not vec:
                            failed += 1
                            continue
                        emb = "[" + ",".join(map(str, vec)) + "]"
                        await conn.execute(
                            "UPDATE knowledge_nodes SET embedding = $1::vector WHERE id = $2",
                            emb,
                            row["id"],
                        )
                        updated += 1
                    except Exception as e:
                        failed += 1
                        logger.debug("backfill node %s: %s", row["id"], e)
            return {"updated": updated, "failed": failed, "candidates": len(rows)}
        except Exception as exc:
            logger.warning("chunked backfill failed, per-node fallback: %s", exc)

        for row in rows:
            try:
                emb = await get_embedding_vector_str(row["content"] or "")
                if not emb:
                    failed += 1
                    continue
                await conn.execute(
                    "UPDATE knowledge_nodes SET embedding = $1::vector WHERE id = $2",
                    emb,
                    row["id"],
                )
                updated += 1
            except Exception as e:
                failed += 1
                logger.debug("backfill node %s: %s", row["id"], e)

        return {"updated": updated, "failed": failed, "candidates": len(rows)}
    finally:
        await conn.close()


async def purge_non_rag_junk(limit: int = 50_000) -> int:
    """Delete obvious non-RAG junk (venv / site-packages PROJECT_FILE). Returns deleted count."""
    import asyncpg

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://admin:secret@localhost:6432/knowledge_os",  # pragma: allowlist secret
    )
    conn = await asyncpg.connect(db_url)
    try:
        status = await conn.execute(
            """
            DELETE FROM knowledge_nodes
            WHERE id IN (
                SELECT id FROM knowledge_nodes
                WHERE content LIKE 'PROJECT_FILE:%/venv/%'
                   OR content LIKE '%/site-packages/%'
                LIMIT $1
            )
            """,
            max(1, int(limit)),
        )
        try:
            return int(str(status).split()[-1])
        except Exception:
            return 0
    finally:
        await conn.close()
