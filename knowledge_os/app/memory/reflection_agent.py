import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta

import asyncpg
from app.memory.journal_manager import ExpertJournalManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ReflectionAgent")

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


class ReflectionAgent:
    """
    Nightly Reflection Agent: Consolidates expert journals into semantic knowledge.
    Implements the 'Reflection' pattern from Generative Agents.
    """

    def __init__(self, pool):
        self.pool = pool
        self.journal_mgr = ExpertJournalManager(pool)

    async def run_reflection_cycle(self):
        """Main cycle to process recent journals and create semantic insights."""
        logger.info("🌙 Starting nightly reflection cycle...")

        # 1. Fetch journals from the last 24 hours that haven't been reflected upon
        async with self.pool.acquire() as conn:
            recent_journals = await conn.fetch("""
                SELECT j.*, e.name as expert_name, e.department
                FROM expert_journals j
                JOIN experts e ON j.expert_id = e.id
                WHERE j.created_at > NOW() - INTERVAL '24 hours'
                  AND (j.metadata->>'reflected')::boolean IS NOT TRUE
                ORDER BY j.importance DESC
                LIMIT 50
            """)

        if not recent_journals:
            logger.info("No new journals to reflect upon.")
            return

        logger.info(f"Processing {len(recent_journals)} journal entries for reflection.")

        # 2. Group journals by department for collective reflection
        dept_groups = {}
        for j in recent_journals:
            dept = j["department"] or "General"
            if dept not in dept_groups:
                dept_groups[dept] = []
            dept_groups[dept].append(j)

        for dept, journals in dept_groups.items():
            await self._reflect_on_department(dept, journals)

        logger.info("✅ Nightly reflection cycle completed.")

    async def _reflect_on_department(self, dept: str, journals: list):
        """Synthesizes insights for a specific department."""
        logger.info(f"Reflecting on department: {dept}")

        # Prepare context for reflection
        journal_texts = []
        for j in journals:
            journal_texts.append(
                f"Expert: {j['expert_name']}\nTask: {j['summary']}\nLearnings: {j['learnings']}"
            )

        combined_context = "\n\n---\n\n".join(journal_texts)

        reflection_prompt = f"""
You are the Corporate Reflection Agent. Analyze these recent task outcomes from the {dept} department and extract 1-3 high-level 'Crystals of Wisdom' (best practices, recurring issues, or strategic insights).

RECENT JOURNALS:
{combined_context}

FORMAT YOUR RESPONSE AS A JSON LIST OF OBJECTS:
[
  {{
    "title": "Short descriptive title",
    "content": "The actual insight or rule to remember",
    "importance": 1-10
  }}
]
"""
        try:
            # Use ai_core to run the reflection
            from ai_core import run_smart_agent_async

            resp = await run_smart_agent_async(
                reflection_prompt, expert_name="Victoria", category="reasoning"
            )

            result_text = str(resp.get("result") if isinstance(resp, dict) else resp)

            # Extract JSON from response
            import re

            json_match = re.search(r"\[.*\]", result_text, re.DOTALL)
            if json_match:
                insights = json.loads(json_match.group(0))
                for insight in insights:
                    await self._store_semantic_insight(dept, insight)

                # Mark journals as reflected
                async with self.pool.acquire() as conn:
                    journal_ids = [j["id"] for j in journals]
                    await conn.execute(
                        """
                        UPDATE expert_journals
                        SET metadata = COALESCE(metadata, '{}'::jsonb) || '{"reflected": true}'::jsonb
                        WHERE id = ANY($1::uuid[])
                    """,
                        journal_ids,
                    )
            else:
                logger.warning(f"Could not parse reflection result for {dept}: {result_text[:200]}")

        except Exception as e:
            logger.error(f"Reflection failed for {dept}: {e}")

    async def _store_semantic_insight(self, dept: str, insight: dict):
        """Stores a distilled insight into knowledge_nodes."""
        try:
            async with self.pool.acquire() as conn:
                # Get domain_id
                domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = $1", dept)

                content = (
                    f"💎 [CRYSTAL OF WISDOM - {dept}]: {insight['title']}\n\n{insight['content']}"
                )
                metadata = {
                    "type": "semantic_memory",
                    "source": "nightly_reflection",
                    "importance": insight.get("importance", 5),
                    "department": dept,
                }

                await conn.execute(
                    """
                    INSERT INTO knowledge_nodes (content, metadata, confidence_score, is_verified, domain_id)
                    VALUES ($1, $2, 0.9, true, $3)
                """,
                    content,
                    json.dumps(metadata),
                    domain_id,
                )
                logger.info(f"Stored semantic insight: {insight['title']}")
        except Exception as e:
            logger.error(f"Failed to store semantic insight: {e}")


async def main():
    pool = await asyncpg.create_pool(DB_URL)
    agent = ReflectionAgent(pool)
    await agent.run_reflection_cycle()
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
