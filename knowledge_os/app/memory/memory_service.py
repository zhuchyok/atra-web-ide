import logging
import uuid
from typing import Any, Dict, List, Optional

from app.long_term_memory import get_ltm
from app.memory.journal_manager import ExpertJournalManager

logger = logging.getLogger("MemoryService")


class MemoryService:
    """
    Unified Memory Facade (Phase 9).
    Provides a single interface for Working, Episodic, and Semantic memory.
    """

    def __init__(self, pool):
        self.pool = pool
        self.journal_mgr = ExpertJournalManager(pool)
        self.ltm = get_ltm()

    async def recall(self, expert_id: uuid.UUID, query: str, limit: int = 5) -> str:
        """
        Recalls a weighted mix of memories for an expert.
        1. Episodic (Recent Journals)
        2. Semantic (Long-term vector nodes)
        """
        # 1. Get Episodic Memory (Journals)
        journals = await self.journal_mgr.format_journal_for_prompt(expert_id, limit=3)

        # 2. Get Semantic Memory (Vector Search)
        semantic_nodes = await self.ltm.recall_memories(query, limit=limit)
        semantic_block = ""
        if semantic_nodes:
            semantic_block = "\n\n## RELEVANT SEMANTIC MEMORY:\n"
            for node in semantic_nodes:
                semantic_block += f"- {node['content'][:500]}\n"

        return journals + semantic_block

    async def record_outcome(
        self,
        expert_id: uuid.UUID,
        task_id: uuid.UUID,
        summary: str,
        learnings: str = None,
        importance: int = 5,
    ):
        """Records a task outcome into episodic memory and potentially LTM."""
        # Save to Journal
        await self.journal_mgr.add_entry(expert_id, task_id, summary, learnings, importance)

        # If very important, also save to LTM (Vector DB)
        if importance >= 8:
            content = f"CRITICAL LEARNING: {summary}\n{learnings or ''}"
            await self.ltm.store_memory(
                content,
                source="expert_journal",
                metadata={"expert_id": str(expert_id), "task_id": str(task_id)},
            )
