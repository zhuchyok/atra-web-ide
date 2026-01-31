"""
[KNOWLEDGE OS] Swarm Orchestrator Engine.
Coordinates multiple AI experts to reach consensus on critical tasks.
Part of the ATRA Singularity framework.
"""

import asyncio
import getpass
import json
import logging
import os
from typing import List

# Third-party imports with fallback
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

# Local project imports with fallback
try:
    from ai_core import run_smart_agent_async
except ImportError:
    async def run_smart_agent_async(prompt, **kwargs):  # pylint: disable=unused-argument
        """Fallback for run_smart_agent_async."""
        return None

logger = logging.getLogger(__name__)

USER_NAME = getpass.getuser()
# Priority: 1. env var, 2. local user (Mac), 3. fallback to admin (Server)
if USER_NAME == 'zhuchyok':
    DEFAULT_DB_URL = f'postgresql://{USER_NAME}@localhost:5432/knowledge_os'
else:
    DEFAULT_DB_URL = 'postgresql://admin:secret@localhost:5432/knowledge_os'

DB_URL = os.getenv('DATABASE_URL', DEFAULT_DB_URL)


class SwarmOrchestrator:
    """
    Swarm War-Room (Singularity v3.0).
    Coordinates multiple experts to reach consensus on critical tasks.
    """

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def assemble_swarm(self, task_description: str, expert_names: List[str]) -> str:
        """Run parallel expert consultations and synthesize a final decision."""
        logger.info("🐝 Assembling Swarm: %s", expert_names)

        # 1. Run parallel experts
        tasks = []
        for name in expert_names:
            prompt = (
                f"ВЫ - {name}. Проанализируйте следующую проблему и дайте свое "
                f"экспертное заключение: {task_description}"
            )
            tasks.append(run_smart_agent_async(prompt, expert_name=name, category="swarm_expert"))

        expert_responses = await asyncio.gather(*tasks)

        # 2. Consensus Synthesis
        synthesis_prompt = (
            "ВЫ - ВИКТОРИЯ, ВЕРХОВНЫЙ КООРДИНАТОР.\n"
            "ЗАДАЧА: Сформируйте финальное решение на основе мнений ваших Директоров.\n\n"
            f"ЗАДАЧА СВОРМА: {task_description}\n\n"
            "МНЕНИЯ ЭКСПЕРТОВ:"
        )
        for name, resp in zip(expert_names, expert_responses):
            synthesis_prompt += f"\n--- {name} ---\n{resp}\n"

        synthesis_prompt += "\nФИНАЛЬНОЕ РЕШЕНИЕ (в стиле ATRA):"

        final_decision = await run_smart_agent_async(
            synthesis_prompt,
            expert_name="Виктория",
            category="swarm_consensus"
        )
        return final_decision

    async def handle_critical_failures(self):
        """Find repeated failures and resolve them via Swarm."""
        if not ASYNCPG_AVAILABLE:
            logger.error("❌ asyncpg is not installed. Swarm orchestration aborted.")
            return "Error: asyncpg missing"

        try:
            conn = await asyncpg.connect(self.db_url)
            # Find logs with failures in the last 2 hours
            failures = await conn.fetch("""
                SELECT user_query, count(*) as fail_count
                FROM interaction_logs
                WHERE (assistant_response LIKE '❌%' OR assistant_response LIKE '⚠️%')
                AND created_at > NOW() - INTERVAL '2 hours'
                GROUP BY user_query
                HAVING count(*) >= 2
                LIMIT 1
            """)

            if not failures:
                await conn.close()
                return "No repeated failures found."

            for fail in failures:
                query = fail['user_query']
                logger.info("🚨 Repeated failure: %s. Triggering Swarm War-Room.", query)

                # Experts for the War-Room
                war_room_experts = ["Дмитрий", "Мария", "Максим"]

                decision = await self.assemble_swarm(
                    f"Повторяющийся сбой на запрос: {query}",
                    war_room_experts
                )

                # Log the swarm decision
                node_content = (
                    f"🐝 SWARM RESOLUTION: Сбой на запрос '{query}' решен консенсусом: "
                    f"{decision[:200]}..."
                )
                node_meta = json.dumps({"type": "swarm_resolution", "query": query})
                await conn.execute("""
                    INSERT INTO knowledge_nodes (domain_id, content, is_verified, confidence_score, metadata)
                    VALUES ((SELECT id FROM domains WHERE name = 'Risk' LIMIT 1), $1, true, 0.99, $2)
                """, node_content, node_meta)

                logger.info("✅ Swarm resolved failure for: %s", query)

            await conn.close()
            return "Swarm cycle finished."
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("SwarmOrchestrator error: %s", exc)
            return f"Error: {exc}"


if __name__ == "__main__":
    swarm_instance = SwarmOrchestrator()
    asyncio.run(swarm_instance.handle_critical_failures())
