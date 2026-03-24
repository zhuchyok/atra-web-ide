"""
[KNOWLEDGE OS] Memory Consolidator Engine.
Consolidates fragmented knowledge nodes into fundamental principles.
"The Dreaming Phase" of Singularity v4.0.
"""

import asyncio
import getpass
import json
import logging
import os

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
if USER_NAME == "zhuchyok":
    DEFAULT_DB_URL = f"postgresql://{USER_NAME}@localhost:6432/knowledge_os"
else:
    DEFAULT_DB_URL = "postgresql://admin:secret@localhost:6432/knowledge_os"

DB_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)


class MemoryConsolidator:
    """
    Phase C of Singularity v4.0.
    Consolidates fragmented knowledge nodes into fundamental principles.
    "The Dreaming Phase"
    """

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def consolidate_memory(self):
        """
        Main consolidation cycle:
        1. Groups nodes by domain.
        2. Uses Victoria to synthesize fundamental principles.
        3. Updates database with consolidated knowledge.
        """
        if not ASYNCPG_AVAILABLE:
            logger.error("❌ asyncpg is not installed. Consolidation aborted.")
            return "Error: asyncpg missing"

        logger.info("🧠 Memory Consolidator: Starting knowledge consolidation...")
        conn = await asyncpg.connect(self.db_url)
        try:
            # 1. Group nodes by domain
            domains = await conn.fetch("SELECT id, name FROM domains")

            for domain in domains:
                nodes = await conn.fetch(
                    """
                    SELECT id, content FROM knowledge_nodes
                    WHERE domain_id = $1 AND confidence_score < 1.0
                    ORDER BY created_at ASC LIMIT 10
                """,
                    domain["id"],
                )

                if len(nodes) < 5:
                    continue

                logger.info("  Processing domain: %s (%d nodes)", domain["name"], len(nodes))

                # 2. Use Victoria to synthesize fundamental principles
                synthesis_prompt = (
                    "ВЫ - Виктория, Главный Координатор. "
                    "Ваша задача - провести «Когнитивную Консолидацию».\n"
                    f"Ниже приведен список разрозненных фактов из домена «{domain['name']}».\n\n"
                    "ФАКТЫ:"
                )
                for i, node in enumerate(nodes):
                    synthesis_prompt += f"\n{i + 1}. {node['content']}"

                synthesis_prompt += (
                    "\n\nЗАДАЧА: Сформулируйте 1-2 фундаментальных принципа или обобщенных знания, "
                    "которые покрывают суть этих фактов. Ваш ответ должен быть глубоким, точным "
                    "и лишенным «воды».\n\n"
                    "ВЕРНИТЕ ТОЛЬКО ТЕКСТ НОВЫХ ЗНАНИЙ."
                )

                consolidated_knowledge = await run_smart_agent_async(
                    synthesis_prompt, expert_name="Виктория", category="memory_consolidation"
                )

                if consolidated_knowledge and len(consolidated_knowledge) > 50:
                    # 3. Insert fundamental knowledge
                    metadata_json = json.dumps(
                        {
                            "source": "memory_consolidator",
                            "merged_nodes": [str(n["id"]) for n in nodes],
                        }
                    )
                    new_id = await conn.fetchval(
                        """
                        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                        VALUES ($1, $2, 1.0, $3, true)
                        RETURNING id
                    """,
                        domain["id"],
                        f"💎 ФУНДАМЕНТАЛЬНОЕ ЗНАНИЕ: {consolidated_knowledge}",
                        metadata_json,
                    )

                    # 4. Mark old nodes as "archived" or remove them
                    # For safety, we just lower their confidence and mark as consolidated
                    await conn.execute(
                        """
                        UPDATE knowledge_nodes SET confidence_score = 0.1,
                        metadata = metadata || ('{"consolidated_into": "' || $1 || '"}')::jsonb
                        WHERE id = ANY($2)
                    """,
                        str(new_id),
                        [n["id"] for n in nodes],
                    )

                    logger.info("✅ Consolidated %d nodes in %s.", len(nodes), domain["name"])

            return "Memory consolidation finished."
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Memory consolidation error: %s", exc)
            return f"Error: {exc}"
        finally:
            await conn.close()


if __name__ == "__main__":
    consolidator_instance = MemoryConsolidator()
    asyncio.run(consolidator_instance.consolidate_memory())
