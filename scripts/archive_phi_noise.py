import asyncio
import asyncpg
import os
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ArchiveNoise")

DB_URL = os.getenv("POSTGRES_DIRECT_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

async def archive_noise():
    conn = await asyncpg.connect(DB_URL)
    try:
        logger.info("🚀 Starting noise archiving for phi3.5:3.8b-stable nodes...")

        # Update metadata to include low_priority: true
        result = await conn.execute("""
            UPDATE knowledge_nodes
            SET metadata = metadata || jsonb_build_object(
                'low_priority', true,
                'archived_at', NOW()::text
            )
            WHERE metadata->>'distilled_by' = 'phi3.5:3.8b-stable'
              AND (metadata->>'low_priority') IS NULL;
        """)

        logger.info(f"✅ Successfully archived {result.split()[-1]} nodes.")

        # Verify
        count = await conn.fetchval("""
            SELECT count(*) FROM knowledge_nodes
            WHERE metadata->>'low_priority' = 'true'
              AND metadata->>'distilled_by' = 'phi3.5:3.8b-stable';
        """)
        logger.info(f"📊 Total archived phi3.5 nodes: {count}")

    except Exception as e:
        logger.error(f"❌ Error during archiving: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(archive_noise())
