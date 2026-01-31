"""
[KNOWLEDGE OS] Synthetic Knowledge Generator.
Accelerator for Singularity: uses Cloud LLM to generate synthetic training data
based on existing knowledge nodes to train local models faster.
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
if USER_NAME == 'zhuchyok':
    DEFAULT_DB_URL = f'postgresql://{USER_NAME}@localhost:5432/knowledge_os'
else:
    DEFAULT_DB_URL = 'postgresql://admin:secret@localhost:5432/knowledge_os'

DB_URL = os.getenv('DATABASE_URL', DEFAULT_DB_URL)

# Use relative path for dataset
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISTILLATION_DATASET_PATH = os.path.join(base_dir, "ai_learning_data", "distillation_dataset.jsonl")


class SyntheticKnowledgeGenerator:
    """
    Accelerator for Singularity: uses Cloud LLM to generate synthetic training data
    based on existing knowledge nodes to train local models faster.
    """

    async def generate_synthetic_samples(self, limit: int = 10):
        """Pick existing knowledge and generate Q&A samples."""
        if not ASYNCPG_AVAILABLE:
            logger.error("❌ asyncpg is not installed. Synthetic generation aborted.")
            return 0

        try:
            conn = await asyncpg.connect(DB_URL)
            # Pick knowledge nodes that are verified but not yet used for synthesis
            nodes = await conn.fetch("""
                SELECT k.id, k.content, d.name as domain
                FROM knowledge_nodes k
                JOIN domains d ON k.domain_id = d.id
                WHERE is_verified = true
                AND (metadata->>'synthesized' IS NULL OR metadata->>'synthesized' = 'false')
                ORDER BY RANDOM()
                LIMIT $1
            """, limit)

            if not nodes:
                await conn.close()
                return 0

            count = 0
            for node in nodes:
                prompt = (
                    "ВЫ - ГЕНЕРАТОР ОБУЧАЮЩИХ ДАННЫХ (УРОВЕНЬ 5).\n"
                    f"НА ОСНОВЕ ФАКТА: \"{node['content']}\" (Домен: {node['domain']})\n\n"
                    "ЗАДАЧА: Сформулируйте 3 разнообразных вопроса, которые Владелец мог бы задать "
                    "по этой теме, и дайте на них идеальные, краткие и технически точные ответы "
                    "в стиле корпорации ATRA.\n\n"
                    "ВЕРНИТЕ ТОЛЬКО JSON LIST:\n"
                    "[\n"
                    "  {\"instruction\": \"Вопрос 1\", \"output\": \"Ответ 1\"},\n"
                    "  ...\n"
                    "]"
                )

                response = await run_smart_agent_async(
                    prompt,
                    expert_name="Виктория",
                    category="synthesis"
                )

                if not response:
                    continue

                try:
                    if "```json" in response:
                        response = response.split("```json")[1].split("```")[0]
                    elif "```" in response:
                        response = response.split("```")[1].split("```")[0]

                    samples = json.loads(response)

                    with open(DISTILLATION_DATASET_PATH, 'a', encoding='utf-8') as f:
                        for s in samples:
                            s['metadata'] = {
                                "type": "synthetic",
                                "source_node_id": str(node['id'])
                            }
                            f.write(json.dumps(s, ensure_ascii=False) + '\n')
                            count += 1

                    # Mark node as synthesized
                    await conn.execute("""
                        UPDATE knowledge_nodes
                        SET metadata = metadata || '{"synthesized": "true"}'::jsonb
                        WHERE id = $1
                    """, node['id'])

                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.error("Error parsing synthetic data for node %s: %s",
                                 node['id'], exc)

            await conn.close()
            return count

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Synthetic generation error: %s", exc)
            return 0


if __name__ == "__main__":
    generator_instance = SyntheticKnowledgeGenerator()
    asyncio.run(generator_instance.generate_synthetic_samples(5))
