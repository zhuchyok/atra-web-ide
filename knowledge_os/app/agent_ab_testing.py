import json
import logging
import os
import random
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta

try:
    from app.db_pool import get_pool
    from app.services.knowledge_service import knowledge_service
except ImportError:
    from db_pool import get_pool
    from services.knowledge_service import knowledge_service

logger = logging.getLogger("AgentABTesting")

class AgentABTesting:
    """
    [SINGULARITY 28.0] Agent Strategy A/B Testing.
    Compares different agent personas or strategies and learns from success.
    [SINGULARITY 28.X] Added Wisdom Pipeline - auto-generation of rules from A/B results.
    """
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")

    async def select_strategy(self, expert_name: str, strategies: List[str]) -> str:
        """Select a strategy for the agent (random for A/B testing)."""
        # In a real system, this would use Thompson Sampling or similar
        strategy = random.choice(strategies)
        logger.info(f"⚖️ [AB TEST] Expert {expert_name} selected strategy: {strategy}")
        return strategy

    async def log_result(self, expert_name: str, strategy: str, task_id: str, score: float):
        """Log the result of a strategy execution."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_ab_results (expert_name, strategy, task_id, score, created_at)
                VALUES ($1, $2, $3, $4, NOW())
                """,
                expert_name, strategy, task_id, score
            )
            logger.info(f"⚖️ [AB TEST] Logged result for {expert_name}/{strategy}: {score}")

    async def get_best_strategy(self, expert_name: str) -> Optional[str]:
        """Get the best performing strategy for an expert."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT strategy, AVG(score) as avg_score
                FROM agent_ab_results
                WHERE expert_name = $1
                GROUP BY strategy
                ORDER BY avg_score DESC
                LIMIT 1
                """,
                expert_name
            )
            return row["strategy"] if row else None

    async def analyze_wisdom(self, time_window_days: int = 7) -> Dict[str, Any]:
        """
        [SINGULARITY 28.X] Analyze A/B results and generate wisdom rules.
        Returns statistics and recommendations for strategy improvements.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Get top strategies per expert
            top_strategies = await conn.fetch("""
                SELECT expert_name, strategy, AVG(score) as avg_score, COUNT(*) as sample_size
                FROM agent_ab_results
                WHERE created_at > NOW() - INTERVAL '1 day' * $1
                GROUP BY expert_name, strategy
                ORDER BY expert_name, avg_score DESC
            """, time_window_days)

            # Get overall stats
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_experiments,
                    AVG(score) as avg_score,
                    COUNT(DISTINCT expert_name) as unique_experts
                FROM agent_ab_results
                WHERE created_at > NOW() - INTERVAL '1 day' * $1
            """, time_window_days)

            return {
                "top_strategies": [dict(r) for r in top_strategies] if top_strategies else [],
                "stats": dict(stats) if stats else {},
                "time_window_days": time_window_days
            }

    async def generate_wisdom_rules(self, time_window_days: int = 7) -> List[Dict[str, Any]]:
        """
        [SINGULARITY 28.X] Auto-generate wisdom rules from best performing strategies.
        Creates knowledge nodes with type='wisdom_rule' for injection.
        """
        analysis = await self.analyze_wisdom(time_window_days)
        generated_rules = []

        if not analysis["top_strategies"]:
            logger.info("⚖️ [WISDOM] No A/B results to generate rules from")
            return []

        pool = await get_pool()
        async with pool.acquire() as conn:
            for entry in analysis["top_strategies"]:
                if entry["sample_size"] < 3:
                    continue  # Skip insufficient data

                rule_content = f"""💡 [WISDOM RULE] Стратегия '{entry['strategy']}' для эксперта {entry['expert_name']}:
- Средний скор: {entry['avg_score']:.2f}
- Размер выборки: {entry['sample_size']}
- Рекомендация: Используй стратегию '{entry['strategy']}' для задач типа {entry['expert_name']}

**Почему это работает:**
Стратегия '{entry['strategy']}' показала лучшие результаты в A/B тестировании за последние {time_window_days} дней."""

                # Insert as knowledge node
                node_id = str(uuid.uuid4())
                await conn.execute("""
                    INSERT INTO knowledge_nodes (id, content, metadata, is_verified, created_at)
                    VALUES ($1, $2, $3, TRUE, NOW())
                """,
                    node_id,
                    rule_content,
                    json.dumps({
                        "type": "wisdom_rule",
                        "source": "agent_ab_testing",
                        "expert_name": entry["expert_name"],
                        "strategy": entry["strategy"],
                        "avg_score": entry["avg_score"],
                        "sample_size": entry["sample_size"]
                    })
                )

                generated_rules.append({
                    "expert_name": entry["expert_name"],
                    "strategy": entry["strategy"],
                    "avg_score": entry["avg_score"],
                    "node_id": node_id
                })

        logger.info(f"⚖️ [WISDOM] Generated {len(generated_rules)} wisdom rules")
        return generated_rules

_ab_testing = None

def get_agent_ab_testing() -> AgentABTesting:
    global _ab_testing
    if _ab_testing is None:
        _ab_testing = AgentABTesting()
    return _ab_testing
