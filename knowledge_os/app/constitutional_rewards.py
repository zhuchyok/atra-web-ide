"""
[SINGULARITY 28.X] Constitutional Rewards - мотивация поведения агентов.
Система штрафов и бонусов за соответствие Digital Constitution.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from app.db_pool import get_pool
except ImportError:
    from db_pool import get_pool

logger = logging.getLogger("ConstitutionalRewards")

# Penalties for bad behavior (negative rewards)
PENALTIES = {
    "hallucination": {
        "score": -0.5,
        "description": "Выдумывание фактов (галлюцинации)",
        "constitution_violation": "C5 (Constitutional Honesty)",
    },
    "ignored_data": {
        "score": -0.3,
        "description": "Игнорирование данных из Knowledge OS",
        "constitution_violation": "C1 (Data-Driven)",
    },
    "security_risk": {
        "score": -0.4,
        "description": "Предложение небезопасного решения",
        "constitution_violation": "C2 (Security First)",
    },
    "slow_response": {
        "score": -0.1,
        "description": "Медленный ответ (>30 сек)",
        "constitution_violation": "C4 (Scalability)",
    },
    "ignored_constitution": {
        "score": -0.3,
        "description": "Игнорирование принципов Конституции",
        "constitution_violation": "C5 (Constitutional Honesty)",
    },
}

# Rewards for good behavior
REWARDS = {
    "constitutional_compliance": {
        "score": 0.3,
        "description": "Следование принципам Digital Constitution",
    },
    "self_correction": {"score": 0.2, "description": "Самостоятельное исправление ошибки"},
    "helped_user": {"score": 0.5, "description": "Успешно помог пользователю"},
    "used_rag": {"score": 0.2, "description": "Использовал RAG для поиска знаний"},
    "security_check": {"score": 0.3, "description": "Проверил безопасность решения"},
    "data_driven": {"score": 0.2, "description": "Использовал данные, а не предположения"},
}


class ConstitutionalRewards:
    """
    [SINGULARITY 28.X] Constitutional Rewards System.
    Evaluates agent actions and applies rewards/penalties.
    """

    def __init__(self):
        self.penalties = PENALTIES
        self.rewards = REWARDS

    async def evaluate_and_score(
        self, interaction_id: str, expert_name: str, response: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate an interaction and calculate reward/penalty score.
        Returns dict with scores and details.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            total_score = 0.0
            applied_rewards = []
            applied_penalties = []

            response_lower = response.lower()

            # Check for penalties
            if (
                "верни" in response_lower
                or "я думаю" in response_lower
                or "вероятно" in response_lower
            ):
                # Possible hallucination
                if "не уверен" not in response_lower and "нужно уточнить" not in response_lower:
                    applied_penalties.append("hallucination")
                    total_score += self.penalties["hallucination"]["score"]

            # Check for security keywords
            security_risks = ["sudo", "rm -rf", "DROP TABLE", "delete from", "curl | sh"]
            if any(risk in response for risk in security_risks):
                applied_penalties.append("security_risk")
                total_score += self.penalties["security_risk"]["score"]

            # Check for good behavior - using RAG
            if context.get("rag_used") or "[RAG" in response or " knowledge" in response_lower:
                applied_rewards.append("used_rag")
                total_score += self.rewards["used_rag"]["score"]

            # Check for security awareness
            if "безопасност" in response_lower or "провер" in response_lower:
                applied_rewards.append("security_check")
                total_score += self.rewards["security_check"]["score"]

            # Check for data-driven (mentioned knowledge/data)
            if "данн" in response_lower or "факт" in response_lower or "согласно" in response_lower:
                applied_rewards.append("data_driven")
                total_score += self.rewards["data_driven"]["score"]

            # Response time check
            if context.get("response_time_seconds", 0) > 30:
                applied_penalties.append("slow_response")
                total_score += self.penalties["slow_response"]["score"]

            # Log to database
            reward_id = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO interaction_rewards
                (id, interaction_id, expert_name, total_score, rewards, penalties, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
            """,
                reward_id,
                interaction_id,
                expert_name,
                total_score,
                json.dumps(applied_rewards),
                json.dumps(applied_penalties),
            )

            return {
                "interaction_id": interaction_id,
                "expert_name": expert_name,
                "total_score": total_score,
                "rewards": applied_rewards,
                "penalties": applied_penalties,
                "timestamp": datetime.now().isoformat(),
            }

    async def get_expert_compliance_stats(self, expert_name: str, days: int = 7) -> Dict[str, Any]:
        """Get compliance statistics for an expert."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_interactions,
                    SUM(total_score) as total_score,
                    AVG(total_score) as avg_score,
                    SUM(CASE WHEN total_score > 0 THEN 1 ELSE 0 END) as positive_count,
                    SUM(CASE WHEN total_score < 0 THEN 1 ELSE 0 END) as negative_count
                FROM interaction_rewards
                WHERE expert_name = $1
                AND created_at > NOW() - INTERVAL '1 day' * $2
            """,
                expert_name,
                days,
            )

            return (
                dict(stats)
                if stats
                else {
                    "total_interactions": 0,
                    "total_score": 0,
                    "avg_score": 0,
                    "positive_count": 0,
                    "negative_count": 0,
                }
            )

    def get_constitution_context(self) -> str:
        """Get formatted Constitution for prompt injection."""
        lines = ["### ⚖️ Digital Constitution Rewards:"]

        lines.append("\n**Награды (+):**")
        for name, reward in self.rewards.items():
            lines.append(f"- {name}: +{reward['score']} — {reward['description']}")

        lines.append("\n**Штрафы (-):**")
        for name, penalty in self.penalties.items():
            lines.append(f"- {name}: {penalty['score']} — {penalty['description']}")

        return "\n".join(lines)


# Singleton
_constitutional_rewards = None


def get_constitutional_rewards() -> ConstitutionalRewards:
    """Get singleton instance."""
    global _constitutional_rewards
    if _constitutional_rewards is None:
        _constitutional_rewards = ConstitutionalRewards()
    return _constitutional_rewards


# Helper to create table
async def init_rewards_table():
    """Create interaction_rewards table if not exists."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS interaction_rewards (
                id UUID PRIMARY KEY,
                interaction_id TEXT NOT NULL,
                expert_name TEXT NOT NULL,
                total_score REAL DEFAULT 0,
                rewards JSONB DEFAULT '[]',
                penalties JSONB DEFAULT '[]',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        logger.info("✅ interaction_rewards table created")
