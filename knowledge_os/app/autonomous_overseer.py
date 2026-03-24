import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import asyncpg

logger = logging.getLogger(__name__)


class AutonomousOverseer:
    """
    [SINGULARITY 21.19] Autonomous Overseer.
    Analyzes logs, metrics, and backlog to generate and assign tasks automatically.
    """

    def __init__(self, db_url: str):
        self.db_url = db_url

    async def run_cycle(self):
        """Main autonomous cycle: Analyze -> Plan -> Assign."""
        logger.info("🕵️ [OVERSEER] Starting autonomous oversight cycle...")

        conn = await asyncpg.connect(self.db_url)
        try:
            # 1. Analyze: Find issues in logs and intellectual capital gaps
            issues = await self._analyze_system_state(conn)

            # 2. Plan & Assign: Create tasks for experts
            for issue in issues:
                await self._create_autonomous_task(conn, issue)

            logger.info(f"✅ [OVERSEER] Cycle complete. Created {len(issues)} autonomous tasks.")
        finally:
            await conn.close()

    async def _analyze_system_state(self, conn) -> List[Dict[str, Any]]:
        """Identifies what needs to be done based on system data."""
        issues = []

        # A. Check for unhandled errors in logs (from knowledge_nodes)
        errors = await conn.fetch("""
            SELECT content, metadata FROM knowledge_nodes
            WHERE metadata->>'type' = 'log_error_detected'
            AND created_at > NOW() - INTERVAL '24 hours'
            LIMIT 5
        """)
        for err in errors:
            issues.append(
                {
                    "title": f"Fix Log Error: {err['content'][:50]}",
                    "description": f"Automatically detected error in logs: {err['content']}",
                    "category": "bugfix",
                    "priority": "high",
                    "assignee_hint": "Игорь",
                }
            )

        # B. Check for business scaling opportunities (Grebenyuk filter)
        # If we have many tasks but few SOPs, Grebenyuk wants more регламентация
        task_count = await conn.fetchval(
            "SELECT COUNT(*) FROM tasks WHERE created_at > NOW() - INTERVAL '7 days'"
        )
        sop_count = await conn.fetchval(
            "SELECT COUNT(*) FROM knowledge_nodes WHERE metadata->>'type' = 'sop_document'"
        )

        if task_count > 10 and sop_count < (task_count / 5):
            issues.append(
                {
                    "title": "Systematization: Create new SOPs for recent tasks",
                    "description": "Grebenyuk Filter: Task/SOP ratio is too low. We need to describe processes to ensure human-independence.",
                    "category": "management",
                    "priority": "medium",
                    "assignee_hint": "Михаил",
                }
            )

        return issues

    async def _create_autonomous_task(self, conn, issue: Dict[str, Any]):
        """Inserts a new task into the database."""
        # Check if similar task already exists to avoid duplicates
        exists = await conn.fetchval(
            "SELECT id FROM tasks WHERE title = $1 AND status != 'completed'", issue["title"]
        )
        if exists:
            return

        # Update: Use metadata for category since 'category' column might not exist
        metadata = {
            "source": "autonomous_overseer",
            "assignee_hint": issue["assignee_hint"],
            "category": issue["category"],
        }

        await conn.execute(
            """
            INSERT INTO tasks (title, description, priority, status, metadata)
            VALUES ($1, $2, $3, 'pending', $4)
        """,
            issue["title"],
            issue["description"],
            issue["priority"],
            json.dumps(metadata),
        )

        logger.info(f"🆕 [OVERSEER] Created task: {issue['title']}")


async def main():
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
    overseer = AutonomousOverseer(db_url)
    await overseer.run_cycle()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
