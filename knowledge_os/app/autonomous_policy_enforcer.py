import asyncio
import logging
import os
from typing import Any, Dict, Optional

import asyncpg

logger = logging.getLogger(__name__)


class AutonomousPolicyEnforcer:
    """
    [SINGULARITY 21.20] Trading Floor Model (Amazon style).
    Dynamically enforces policies and limits based on expert performance.
    """

    def __init__(self, db_url: str):
        self.db_url = db_url

    async def get_expert_policy(self, expert_name: str) -> Dict[str, Any]:
        """Returns dynamic limits for the expert."""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                row = await conn.fetchrow(
                    """
                    SELECT performance_score, specialization_level
                    FROM experts WHERE name = $1
                """,
                    expert_name,
                )

                if not row:
                    return self._default_policy()

                score = row["performance_score"] or 0.0
                level = row["specialization_level"] or "PRO"

                # Логика "Trading Floor": чем выше score, тем больше прав
                policy = {
                    "max_tokens": 4000 if level == "ELITE" else 2000,
                    "can_mutate_code": score > 0.8,
                    "can_access_secrets": level == "ELITE" and score > 0.9,
                    "execution_priority": "high" if score > 0.7 else "normal",
                }

                logger.info(f"🛡️ [POLICY] Applied policy for {expert_name} (Score: {score})")
                return policy
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Policy enforcement error: {e}")
            return self._default_policy()

    def _default_policy(self) -> Dict[str, Any]:
        return {
            "max_tokens": 1000,
            "can_mutate_code": False,
            "can_access_secrets": False,
            "execution_priority": "low",
        }


_policy_enforcer = None


def get_policy_enforcer():
    global _policy_enforcer
    if _policy_enforcer is None:
        db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
        _policy_enforcer = AutonomousPolicyEnforcer(db_url)
    return _policy_enforcer
