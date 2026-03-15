"""
[SINGULARITY 21.12] Success Retriever.
Finds relevant past successful tasks to provide few-shot examples to Victoria.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


class SuccessRetriever:
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

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

                # [SINGULARITY 21.18] Success Retrieval Audit: Log efficiency metrics
                try:
                    # Estimate time saved: ~2 minutes per successful example (avoiding re-thinking)
                    time_saved_sec = len(rows) * 120
                    await conn.execute(
                        """
                        INSERT INTO knowledge_nodes (content, metadata)
                        VALUES ($1, $2)
                    """,
                        f"Success Retrieval Audit for: {query[:100]}",
                        {
                            "type": "success_retrieval_audit",
                            "expert_name": expert_name,
                            "examples_found": len(rows),
                            "time_saved_seconds": time_saved_sec,
                            "query_preview": query[:200],
                        },
                    )
                    logger.info(
                        f"📊 [AUDIT] Logged Success Retrieval efficiency: {time_saved_sec}s saved."
                    )
                except Exception as ae:
                    logger.debug(f"Audit log error: {ae}")

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
