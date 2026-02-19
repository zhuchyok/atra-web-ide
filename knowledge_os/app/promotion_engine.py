import asyncio
import logging
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

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
    # Try to use existing pool if available from other modules, or create new
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    return await asyncpg.create_pool(db_url, min_size=1, max_size=5)

async def check_and_promote_mutations(conn: Optional[asyncpg.Connection] = None):
    """
    Queries expert_mutations for active 'shadow' mutations and promotes them if they meet thresholds.
    Can accept an existing connection or create its own pool.
    """
    logger.info("🚀 Starting Shadow Prompt Promotion Engine...")
    
    should_close_conn = False
    if conn is None:
        pool = await get_db_pool()
        if not pool:
            logger.error("❌ asyncpg not installed or pool not available.")
            return
        conn = await pool.acquire()
        should_close_conn = True

    try:
        # 1. Query active shadow mutations that meet the minimum test threshold
        mutations = await conn.fetch("""
            SELECT id, expert_id, mutated_prompt, win_count, total_tests, base_version
            FROM expert_mutations
            WHERE status = 'shadow' AND total_tests >= $1
        """, MIN_TESTS)

        promoted_count = 0
        for mut in mutations:
            total = mut['total_tests']
            win_count = mut['win_count']
            win_rate = win_count / total if total > 0 else 0
            
            if win_rate > WIN_RATE_THRESHOLD:
                logger.info(f"🌟 Promoting mutation {mut['id']} for expert {mut['expert_id']} (win_rate: {win_rate:.2%})")
                
                async with conn.transaction():
                    # A. Update expert's system prompt and version
                    # We check if 'version' column exists in experts table (it should based on Task 4 requirements)
                    await conn.execute("""
                        UPDATE experts
                        SET system_prompt = $1,
                            version = COALESCE(version, 0) + 1
                        WHERE id = $2
                    """, mut['mutated_prompt'], mut['expert_id'])

                    # B. Update this mutation's status to 'promoted'
                    await conn.execute("""
                        UPDATE expert_mutations
                        SET status = 'promoted',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                    """, mut['id'])

                    # C. Archive other shadow mutations for the same expert
                    await conn.execute("""
                        UPDATE expert_mutations
                        SET status = 'archived',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE expert_id = $1 AND id != $2 AND status = 'shadow'
                    """, mut['expert_id'], mut['id'])

                    # D. Log the promotion as an 'architectural_lesson' to knowledge_nodes
                    expert_info = await conn.fetchrow("SELECT name FROM experts WHERE id = $1", mut['expert_id'])
                    expert_name = expert_info['name'] if expert_info else str(mut['expert_id'])
                    
                    content = (f"Architectural Lesson: Expert '{expert_name}' system prompt was evolved and promoted. "
                              f"The new prompt achieved a {win_rate:.2%} win rate over {total} shadow tests. "
                              f"Mutation ID: {mut['id']}.")
                    
                    metadata = json.dumps({
                        "type": "architectural_lesson",
                        "subtype": "prompt_promotion",
                        "expert_id": str(mut['expert_id']),
                        "expert_name": expert_name,
                        "mutation_id": str(mut['id']),
                        "win_rate": win_rate,
                        "total_tests": total,
                        "base_version": mut['base_version'],
                        "promoted_at": datetime.now().isoformat()
                    })

                    # Try to find a 'System' or 'Meta' domain, fallback to first available
                    domain_id = await conn.fetchval("SELECT id FROM domains WHERE name IN ('System', 'Meta', 'AI') LIMIT 1")
                    if not domain_id:
                        domain_id = await conn.fetchval("SELECT id FROM domains LIMIT 1")

                    await conn.execute("""
                        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, source_ref)
                        VALUES ($1, $2, 1.0, $3, TRUE, 'promotion_engine')
                    """, domain_id, content, metadata)
                
                promoted_count += 1

        if promoted_count > 0:
            logger.info(f"✅ Promotion cycle finished. Promoted {promoted_count} mutations.")
        else:
            logger.info("ℹ️ No mutations met promotion thresholds this cycle.")

    finally:
        if should_close_conn and conn:
            pool = conn.get_pool()
            await pool.release(conn)
            await pool.close()

async def run_promotion_cycle():
    """Entry point for nightly learner or manual trigger."""
    try:
        await check_and_promote_mutations()
    except Exception as e:
        logger.error(f"❌ Error in promotion cycle: {e}", exc_info=True)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(run_promotion_cycle())
