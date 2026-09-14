import logging
import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
import uuid

logger = logging.getLogger(__name__)

ALLOWED_MEMORY_TYPES = {"authoritative", "episodic", "transient", "noise"}

class ExpertJournalManager:
    """
    Manages episodic memory for experts via 'Journals'.
    Each entry represents a task outcome, learnings, and importance.
    """

    def __init__(self, pool):
        self.pool = pool

    @staticmethod
    def _normalize_memory_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Normalize episodic memory metadata for trust-lane routing.
        KISS: enforce a small stable schema with safe defaults.
        """
        raw = dict(metadata or {})
        memory_type = str(raw.get("memory_type", "episodic")).strip().lower()
        if memory_type not in ALLOWED_MEMORY_TYPES:
            memory_type = "episodic"

        try:
            confidence = float(raw.get("confidence", 0.7))
        except Exception:
            confidence = 0.7
        confidence = max(0.0, min(1.0, confidence))

        source = str(raw.get("source", "expert_journal")).strip() or "expert_journal"
        policy_version = str(raw.get("policy_version", "v1")).strip() or "v1"
        used_in_decision = bool(raw.get("used_in_decision", False))
        expires_at = raw.get("expires_at")
        if not expires_at:
            expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

        return {
            **raw,
            "memory_type": memory_type,
            "confidence": confidence,
            "source": source,
            "policy_version": policy_version,
            "used_in_decision": used_in_decision,
            "expires_at": expires_at,
        }

    async def add_entry(self, expert_id: uuid.UUID, task_id: Optional[uuid.UUID],
                        summary: str, learnings: Optional[str] = None,
                        importance: int = 5, metadata: Dict[str, Any] = None):
        """Adds a new episodic memory entry for an expert."""
        try:
            normalized_meta = self._normalize_memory_metadata(metadata)
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO expert_journals (expert_id, task_id, summary, learnings, importance, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, expert_id, task_id, summary, learnings, importance, json.dumps(normalized_meta))
                logger.info(f"Added journal entry for expert {expert_id}")
        except Exception as e:
            logger.error(f"Failed to add journal entry: {e}")

    async def get_recent_entries(self, expert_id: uuid.UUID, limit: int = 5,
                                 min_importance: int = 1) -> List[Dict[str, Any]]:
        """Retrieves recent high-importance journal entries for an expert."""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT summary, learnings, importance, created_at, metadata
                    FROM expert_journals
                    WHERE expert_id = $1 AND importance >= $2
                    ORDER BY created_at DESC
                    LIMIT $3
                """, expert_id, min_importance, limit)
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to fetch journal entries: {e}")
            return []

    async def format_journal_for_prompt(self, expert_id: uuid.UUID, limit: int = 5, min_importance: int = 5) -> str:
        """Formats recent journal entries into a string for LLM prompt injection."""
        entries = await self.get_recent_entries(expert_id, limit=limit, min_importance=min_importance)
        if not entries:
            return ""

        header = "\n\n## YOUR RECENT EXPERIENCE (JOURNAL):\n"
        formatted_entries = []
        for entry in entries:
            dt = entry['created_at'].strftime("%Y-%m-%d %H:%M")
            item = f"### [{dt}] Importance: {entry['importance']}/10\n"
            item += f"**Summary**: {entry['summary']}\n"
            if entry['learnings']:
                item += f"**Learnings**: {entry['learnings']}\n"
            formatted_entries.append(item)

        return header + "\n".join(formatted_entries)
