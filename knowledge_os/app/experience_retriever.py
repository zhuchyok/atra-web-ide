"""
[SINGULARITY 20.0] Experience Retriever.
Finds relevant past failures and mentorship notes to provide proactive warnings to experts.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


class ExperienceRetriever:
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def get_relevant_warnings(self, query: str, expert_name: str, limit: int = 2) -> str:
        """
        Retrieves mentorship notes and failed tasks relevant to the current query.
        """
        try:
            from semantic_cache import get_embedding

            embedding = await get_embedding(query)
            if not embedding:
                return ""

            conn = await asyncpg.connect(self.db_url)
            try:
                # 1. Search for relevant Mentorship Notes for this expert
                mentorship_rows = await conn.fetch(
                    """
                    SELECT content, (1 - (embedding <=> $1::vector)) as similarity
                    FROM knowledge_nodes
                    WHERE metadata->>'type' = 'mentorship_note'
                      AND metadata->>'target_expert' = $2
                      AND embedding IS NOT NULL
                    ORDER BY similarity DESC
                    LIMIT $3
                """,
                    embedding,
                    expert_name,
                    limit,
                )

                # 2. Search for similar FAILED tasks to learn from mistakes
                failed_tasks = await conn.fetch(
                    """
                    SELECT title, metadata->>'error' as error, (1 - (embedding <=> $1::vector)) as similarity
                    FROM tasks
                    WHERE status = 'failed'
                      AND embedding IS NOT NULL
                    ORDER BY similarity DESC
                    LIMIT $2
                """,
                    embedding,
                    limit,
                )

                warnings = []

                if mentorship_rows:
                    for row in mentorship_rows:
                        if row["similarity"] > 0.7:
                            warnings.append(f"⚠️ СОВЕТ ИЗ ПРОШЛОГО АУДИТА: {row['content']}")

                if failed_tasks:
                    for task in failed_tasks:
                        if task["similarity"] > 0.7:
                            error_msg = task["error"] or "Неизвестная ошибка"
                            warnings.append(
                                f"🚨 ПРЕДУПРЕЖДЕНИЕ (Похожая задача '{task['title']}' провалилась): {error_msg[:200]}"
                            )

                if not warnings:
                    return ""

                return "\n### 🧠 ГОЛОС ОПЫТА (PREDICTIVE WARNINGS):\n" + "\n".join(warnings) + "\n"

            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"Experience retrieval error: {e}")
            return ""


async def get_experience_context(query: str, expert_name: str) -> str:
    retriever = ExperienceRetriever()
    return await retriever.get_relevant_warnings(query, expert_name)
