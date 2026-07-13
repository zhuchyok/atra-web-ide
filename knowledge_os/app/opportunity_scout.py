import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List

try:
    from ai_core import run_smart_agent_async
    from app.db_pool import get_pool
    from app.event_bus import Event, EventType
    from app.memory.memory_service import MemoryService
except ImportError:
    # Fallback for direct execution
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ai_core import run_smart_agent_async
    from db_pool import get_pool
    from event_bus import Event, EventType
    from memory.memory_service import MemoryService

logger = logging.getLogger("OpportunityScout")


class OpportunityScout:
    """
    [SINGULARITY 10.0] Proactive agent that scans journals and knowledge nodes
    to identify gaps, optimizations, and new goals.
    """

    def __init__(self, pool):
        self.pool = pool
        self.memory_svc = MemoryService(pool)

    async def scan_and_generate_goals(self):
        """Main loop for proactive goal setting."""
        logger.info("🔭 [SCOUT] Starting opportunity scan...")

        # 1. Fetch recent episodic memories (last 12h)
        async with self.pool.acquire() as conn:
            recent_journals = await conn.fetch("""
                SELECT j.summary, j.learnings, e.name as expert_name, e.role
                FROM expert_journals j
                JOIN experts e ON j.expert_id = e.id
                WHERE j.created_at > NOW() - INTERVAL '12 hours'
                ORDER BY j.importance DESC
                LIMIT 20
            """)

        if not recent_journals:
            logger.info("🔭 [SCOUT] No recent journals to analyze. Skipping.")
            return

        # 2. Prepare context for LLM
        context = "\n".join(
            [
                f"Expert: {j['expert_name']} ({j['role']})\nSummary: {j['summary']}\nLearnings: {j['learnings']}"
                for j in recent_journals
            ]
        )

        prompt = f"""
        You are the OpportunityScout for the Singularity Multi-Agent Corporation.
        Your goal is to analyze the recent experiences of our experts and identify
        3 high-impact proactive tasks that will improve our system, code, or knowledge.

        RECENT EXPERIENCES:
        {context}

        TASK:
        Identify 3 proactive tasks. For each task, provide:
        1. Title (start with [PROACTIVE])
        2. Description (why this is needed and what to do)
        3. Priority (low, medium, high)
        4. Target Expert Role (e.g., Backend, QA, ML)

        Return the result as a JSON list of objects.
        """

        try:
            # Use a capable model for strategy
            response = await run_smart_agent_async(
                prompt, expert_name="OpportunityScout", category="strategic"
            )

            # Parse response (assuming structured JSON from run_smart_agent_async)
            goals = response.get("result") if isinstance(response, dict) else response
            if isinstance(goals, str):
                # Attempt to extract JSON if it's a string
                import re

                match = re.search(r"\[.*\]", goals, re.DOTALL)
                if match:
                    goals = json.loads(match.group())

            if not isinstance(goals, list):
                logger.warning(f"🔭 [SCOUT] Unexpected response format: {type(goals)}")
                return

            # 3. Create tasks in DB
            for goal in goals:
                title = goal.get("title", "[PROACTIVE] New Goal")
                description = goal.get("description", "")
                priority = goal.get("priority", "medium")
                role = goal.get("target_expert_role", "General")

                # Find expert ID by role (simple mapping or query)
                async with self.pool.acquire() as conn:
                    expert = await conn.fetchrow(
                        "SELECT id FROM experts WHERE role ILIKE $1 LIMIT 1", f"%{role}%"
                    )
                    assignee_id = expert["id"] if expert else None

                from app.db_pool import create_task_safe

                task_id = await create_task_safe(
                    title=title,
                    description=description,
                    priority=priority,
                    project_context="proactive_autonomy",
                    assignee_expert_id=assignee_id,
                    metadata={"source": "opportunity_scout", "proactive": True},
                )

                if task_id:
                    logger.info(f"🚀 [SCOUT] Proactive task created: {title}")

        except Exception as e:
            logger.error(f"❌ [SCOUT] Failed to generate goals: {e}")


async def run_scout_cycle():
    from app.db_pool import get_pool

    pool = await get_pool()
    scout = OpportunityScout(pool)
    await scout.scan_and_generate_goals()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scout_cycle())
