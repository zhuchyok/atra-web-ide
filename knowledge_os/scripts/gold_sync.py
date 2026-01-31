"""
GOLD SYNC: Синхронизация узлов и экспертов в локальную Knowledge OS.
После миграции всё хранится локально; удалённый источник только по GOLD_DB_URL (если нужен повторный подтяг).
"""

import asyncio
import logging
import os

# Third-party imports
try:
    import asyncpg  # type: ignore
except ImportError:
    asyncpg = None  # type: ignore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Единая локальная БД (всё уже перенесено сюда)
DB_URL_LOCAL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
# Удалённый источник только если явно задан (для повторного подтяга; по умолчанию = локальная)
GOLD_DB_URL = os.getenv('GOLD_DB_URL', DB_URL_LOCAL)

class GoldSync:
    """Class to handle synchronization between remote Gold DB and local DB."""
    def __init__(self, local_db_url: str = DB_URL_LOCAL):
        self.local_db_url = local_db_url

    async def sync_db_nodes(self):
        """Directly pulls nodes from the remote DB to local DB."""
        if asyncpg is None:
            logger.error("asyncpg is not installed. Cannot sync nodes.")
            return

        logger.info("🚀 Syncing nodes (source: %s)...", GOLD_DB_URL.split('@')[1].split('/')[0] if '@' in GOLD_DB_URL else "local")
        
        try:
            remote_conn = await asyncpg.connect(GOLD_DB_URL, timeout=15)
            local_conn = await asyncpg.connect(self.local_db_url)
            
            # Get domains first to map IDs
            remote_domains = await remote_conn.fetch("SELECT id, name, description FROM domains")
            for d in remote_domains:
                await local_conn.execute("""
                    INSERT INTO domains (id, name, description)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (id) DO UPDATE SET 
                        name = EXCLUDED.name, 
                        description = EXCLUDED.description
                """, d['id'], d['name'], d['description'])
            
            # Sync nodes in batches
            count = await remote_conn.fetchval("SELECT count(*) FROM knowledge_nodes")
            logger.info("Found %d nodes on remote server. Starting sync...", count)
            
            batch_size = 500
            synced = 0
            for offset in range(0, count, batch_size):
                nodes = await remote_conn.fetch(
                    f"SELECT * FROM knowledge_nodes LIMIT {batch_size} OFFSET {offset}"
                )
                for n in nodes:
                    await local_conn.execute("""
                        INSERT INTO knowledge_nodes (
                            domain_id, content, embedding, source_ref, 
                            is_verified, confidence_score, metadata
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT DO NOTHING
                    """, n['domain_id'], n['content'], n['embedding'], n['source_ref'], 
                        n['is_verified'], n['confidence_score'], n['metadata'])
                synced += len(nodes)
                logger.info("  Synced %d/%d nodes...", synced, count)

            await remote_conn.close()
            await local_conn.close()
            logger.info("✅ DB Sync complete. %d nodes processed.", synced)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("❌ DB Sync failed: %s", e)

    async def sync_experts(self):
        """Sync experts from the remote DB."""
        if asyncpg is None:
            logger.error("asyncpg is not installed. Cannot sync experts.")
            return

        logger.info("👥 Syncing experts...")
        try:
            remote_conn = await asyncpg.connect(GOLD_DB_URL, timeout=15)
            local_conn = await asyncpg.connect(self.local_db_url)
            
            experts = await remote_conn.fetch("SELECT * FROM experts")
            for e in experts:
                await local_conn.execute("""
                    INSERT INTO experts (id, name, role, system_prompt, department, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (id) DO UPDATE SET 
                        name = EXCLUDED.name, 
                        role = EXCLUDED.role, 
                        system_prompt = EXCLUDED.system_prompt,
                        department = EXCLUDED.department,
                        metadata = EXCLUDED.metadata
                """, e['id'], e['name'], e['role'], e['system_prompt'], 
                    e['department'], e['metadata'])
            
            await remote_conn.close()
            await local_conn.close()
            logger.info("✅ Expert sync complete. Total: %d", len(experts))
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("❌ Expert sync failed: %s", e)

async def main():
    """Main entry point for the sync process."""
    sync_engine = GoldSync()
    await sync_engine.sync_experts()
    await sync_engine.sync_db_nodes()

if __name__ == "__main__":
    asyncio.run(main())
