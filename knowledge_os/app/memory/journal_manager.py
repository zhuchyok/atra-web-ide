import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExpertJournalManager:
    """
    Manages episodic memory for experts via 'Journals'.
    Each entry represents a task outcome, learnings, and importance.
    """

    def __init__(self, pool):
        self.pool = pool

    async def add_entry(
        self,
        expert_id: uuid.UUID,
        task_id: Optional[uuid.UUID],
        summary: str,
        learnings: Optional[str] = None,
        importance: int = 5,
        metadata: Dict[str, Any] = None,
    ):
        """Adds a new episodic memory entry for an expert."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO expert_journals (expert_id, task_id, summary, learnings, importance, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """,
                    expert_id,
                    task_id,
                    summary,
                    learnings,
                    importance,
                    json.dumps(metadata or {}),
                )
                logger.info(f"Added journal entry for expert {expert_id}")
        except Exception as e:
            logger.error(f"Failed to add journal entry: {e}")

    async def get_recent_entries(
        self, expert_id: uuid.UUID, limit: int = 5, min_importance: int = 1
    ) -> List[Dict[str, Any]]:
        """Retrieves recent high-importance journal entries for an expert."""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT summary, learnings, importance, created_at, metadata
                    FROM expert_journals
                    WHERE expert_id = $1 AND importance >= $2
                    ORDER BY created_at DESC
                    LIMIT $3
                """,
                    expert_id,
                    min_importance,
                    limit,
                )
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to fetch journal entries: {e}")
            return []

    async def format_journal_for_prompt(
        self, expert_id: uuid.UUID, limit: int = 5, min_importance: int = 5
    ) -> str:
        """Formats recent journal entries into a string for LLM prompt injection."""
        entries = await self.get_recent_entries(
            expert_id, limit=limit, min_importance=min_importance
        )
        if not entries:
            return ""

        header = "\n\n## YOUR RECENT EXPERIENCE (JOURNAL):\n"
        formatted_entries = []
        for entry in entries:
            dt = entry["created_at"].strftime("%Y-%m-%d %H:%M")
            item = f"### [{dt}] Importance: {entry['importance']}/10\n"
            item += f"**Summary**: {entry['summary']}\n"
            if entry["learnings"]:
                item += f"**Learnings**: {entry['learnings']}\n"
            formatted_entries.append(item)

        return header + "\n".join(formatted_entries)
