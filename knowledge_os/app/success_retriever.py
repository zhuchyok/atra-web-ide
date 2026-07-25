"""
[SINGULARITY 21.12] Success Retriever.
Finds relevant past successful tasks to provide few-shot examples to Victoria.
"""

import asyncio
import json
import logging
import os
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:secret@localhost:6432/knowledge_os",  # pragma: allowlist secret
)

# Audit nodes were flooding KB (~3–4k/hour). Default: at most 1 audit / expert / hour.
SUCCESS_AUDIT_ENABLED = os.getenv("SUCCESS_AUDIT_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)
SUCCESS_AUDIT_COOLDOWN_MIN = max(1, int(os.getenv("SUCCESS_AUDIT_COOLDOWN_MIN", "60")))
SUCCESS_AUDIT_SAMPLE_RATE = float(os.getenv("SUCCESS_AUDIT_SAMPLE_RATE", "1.0"))


class SuccessRetriever:
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def _should_write_audit(self, conn: Any, expert_name: Optional[str]) -> bool:
        if not SUCCESS_AUDIT_ENABLED:
            return False
        if SUCCESS_AUDIT_SAMPLE_RATE < 1.0:
            import random

            if random.random() > max(0.0, min(1.0, SUCCESS_AUDIT_SAMPLE_RATE)):
                return False
        expert_key = (expert_name or "_global").strip() or "_global"
        try:
            recent = await conn.fetchval(
                """
                SELECT 1
                FROM knowledge_nodes
                WHERE metadata->>'type' = 'success_retrieval_audit'
                  AND COALESCE(metadata->>'expert_name', '_global') = $1
                  AND created_at > NOW() - make_interval(mins => $2::int)
                LIMIT 1
                """,
                expert_key,
                SUCCESS_AUDIT_COOLDOWN_MIN,
            )
            return recent is None
        except Exception as e:
            logger.debug("Success audit cooldown check failed: %s", e)
            return False

    async def get_relevant_successes(
        self,
        query: str,
        limit: int = 2,
        min_similarity: float = 0.7,
        expert_name: Optional[str] = None,
    ) -> str:
        """
        Retrieves successful tasks relevant to the current query.
        """
        try:
            # Import get_embedding from semantic_cache
            try:
                from semantic_cache import get_embedding
            except ImportError:
                from app.semantic_cache import get_embedding

            embedding = await get_embedding(query)
            if not embedding:
                return ""

            conn = await asyncpg.connect(self.db_url)
            try:
                # [SINGULARITY 21.17] Filter by expert if provided
                expert_filter = ""
                params = [str(embedding), min_similarity, limit]

                if expert_name:
                    # Get expert ID first
                    expert_row = await conn.fetchrow(
                        "SELECT id FROM experts WHERE name = $1", expert_name
                    )
                    if expert_row:
                        expert_filter = "AND assignee_expert_id = $4"
                        params.append(expert_row["id"])

                # Search for similar COMPLETED tasks to learn from successes
                rows = await conn.fetch(
                    f"""
                    SELECT title, description, result, (1 - (embedding <=> $1::vector)) as similarity
                    FROM tasks
                    WHERE status = 'completed'
                      AND embedding IS NOT NULL
                      AND (1 - (embedding <=> $1::vector)) >= $2
                      {expert_filter}
                    ORDER BY similarity DESC
                    LIMIT $3
                """,
                    *params,
                )

                if not rows:
                    return ""

                # [SINGULARITY 21.18] Success Retrieval Audit — throttled (cooldown / sample)
                try:
                    if await self._should_write_audit(conn, expert_name):
                        time_saved_sec = len(rows) * 120
                        domain_id = await conn.fetchval(
                            """
                            SELECT id FROM domains
                            WHERE name IN ('Wisdom & Heuristics', 'Mentorship', 'SOP')
                            ORDER BY CASE name
                                WHEN 'Wisdom & Heuristics' THEN 0
                                WHEN 'Mentorship' THEN 1
                                ELSE 2
                            END
                            LIMIT 1
                            """
                        )
                        if domain_id is None:
                            domain_id = await conn.fetchval(
                                "INSERT INTO domains (name) VALUES ('Wisdom & Heuristics') RETURNING id"
                            )
                        meta_kn = json.dumps(
                            {
                                "type": "success_retrieval_audit",
                                "expert_name": expert_name or "_global",
                                "examples_found": len(rows),
                                "time_saved_seconds": time_saved_sec,
                                "query_preview": query[:200],
                            }
                        )
                        await conn.execute(
                            """
                            INSERT INTO knowledge_nodes
                                (domain_id, content, confidence_score, metadata, is_verified)
                            VALUES ($1, $2, 0.8, $3::jsonb, true)
                            """,
                            domain_id,
                            f"Success Retrieval Audit for: {query[:100]}",
                            meta_kn,
                        )
                        logger.info(
                            "📊 [AUDIT] Logged Success Retrieval efficiency: %ss saved.",
                            time_saved_sec,
                        )
                except Exception as ae:
                    logger.warning(f"Audit log error: {ae}")

                successes = []
                for row in rows:
                    title = row["title"] or "Без названия"
                    desc = (row["description"] or "")[:300]
                    res = (row["result"] or "")[:500]
                    sim = row["similarity"]

                    successes.append(
                        f"✅ УСПЕШНЫЙ ПРИМЕР [sim={sim:.2f}]:\n"
                        f"Задача: {title}\n"
                        f"Описание: {desc}...\n"
                        f"Решение: {res}...\n"
                    )

                if not successes:
                    return ""

                return (
                    "\n### 🏆 КОЛЛЕКТИВНЫЙ ОПЫТ (SUCCESS RETRIEVAL):\n"
                    + "\n".join(successes)
                    + "\n"
                )

            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"Success retrieval error: {e}")
            return ""


async def get_success_context(query: str, limit: int = 2, expert_name: Optional[str] = None) -> str:
    retriever = SuccessRetriever()
    return await retriever.get_relevant_successes(query, limit=limit, expert_name=expert_name)
