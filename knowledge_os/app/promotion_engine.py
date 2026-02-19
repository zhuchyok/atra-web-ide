import asyncio
import logging
import os
import json
from datetime import datetime
from typing import List, Dict, Any

try:
    import asyncpg
except ImportError:
    asyncpg = None

logger = logging.getLogger(__name__)

# Thresholds for promotion
MIN_TESTS = 50
WIN_RATE_THRESHOLD = 0.65

async def get_db_pool():
    if asyncpg is None:
        return None
    return await asyncpg.create_pool(
        os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os"),
        min_size=1,
        max_size=5
    )

async def check_and_promote_mutations():
    """
    Queries expert_mutations for active 'shadow' mutations and promotes them if they meet thresholds.
    """
    logger.info("🚀 Starting Shadow Prompt Promotion Engine...")
    pool = await get_db_pool()
    if not pool:
        logger.error("❌ asyncpg not installed or pool not available.")
        return

    async with pool.acquire() as conn:
        # 1. Query active shadow mutations
        mutations = await conn.fetch("""
            SELECT id, expert_id, mutated_prompt, win_count, total_tests, base_version
            FROM expert_mutations
            WHERE status = 'shadow' AND total_tests >= $1
        """, MIN_TESTS)

        promoted_count = 0
        for mut in mutations:
            win_rate = mut['win_count'] / mut['total_tests'] if mut['total_tests'] > 0 else 0
            
            if win_rate > WIN_RATE_THRESHOLD:
                logger.info(f"🌟 Promoting mutation {mut['id']} for expert {mut['expert_id']} (win_rate: {win_rate:.2%})")
                
                async with conn.transaction():
                    # A. Update expert's system prompt and version
                    await conn.execute("""
                        UPDATE experts
                        SET system_prompt = $1,
                            version = version + 1
                        WHERE id = $2
                    """, mut['mutated_prompt'], mut['expert_id'])

                    # B. Update this mutation's status to 'promoted'
                    await conn.execute("""
                        UPDATE expert_mutations
                        SET status = 'promoted',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                    """, mut['id'])

                    # C. Archive other mutations for the same expert
                    await conn.execute("""
                        UPDATE expert_mutations
                        SET status = 'archived',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE expert_id = $1 AND id != $2 AND status = 'shadow'
                    """, mut['expert_id'], mut['id'])

                    # D. Log the promotion to knowledge_nodes
                    expert_info = await conn.fetchrow("SELECT name FROM experts WHERE id = $1", mut['expert_id'])
                    expert_name = expert_info['name'] if expert_info else str(mut['expert_id'])
                    
                    content = (f"Prompt Promotion: Expert '{expert_name}' prompt was promoted to a new version. "
                              f"Mutation ID: {mut['id']}, Win Rate: {win_rate:.2%}, Total Tests: {mut['total_tests']}.")
                    
                    metadata = json.dumps({
                        "type": "prompt_promotion",
                        "expert_id": str(mut['expert_id']),
                        "mutation_id": str(mut['id']),
                        "win_rate": win_rate,
                        "total_tests": mut['total_tests'],
                        "base_version": mut['base_version']
                    })

                    await conn.execute("""
                        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                        VALUES ((SELECT id FROM domains WHERE name = 'System' LIMIT 1), $1, 1.0, $2, TRUE)
                    """, content, metadata)
                
                promoted_count += 1

        logger.info(f"✅ Promotion cycle finished. Promoted {promoted_count} mutations.")

    await pool.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(check_and_promote_mutations())
