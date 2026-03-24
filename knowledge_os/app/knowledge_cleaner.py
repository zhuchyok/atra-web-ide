import asyncio
import os
from datetime import datetime

import asyncpg
from resource_manager import acquire_resource_lock

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


async def archive_old_knowledge():
    async with acquire_resource_lock("knowledge_cleaner"):
        print(f"[{datetime.now()}] 🧹 Starting Knowledge Cleaner (Archiving Phase)...")
        conn = await asyncpg.connect(DB_URL)

        # 1. Находим узлы, которые не использовались > 30 дней и имеют 0 использований
        # (Исключаем верифицированные знания высокого качества или кросс-доменные гипотезы)
        old_nodes = await conn.fetch("""
            SELECT id FROM knowledge_nodes
            WHERE usage_count = 0
            AND created_at < NOW() - INTERVAL '30 days'
            AND confidence_score < 0.9
            AND (metadata->>'source' IS NULL OR metadata->>'source' != 'cross_domain_linker')
            LIMIT 500
        """)

        if not old_nodes:
            print("✅ No nodes to archive.")
            await conn.close()
            return

        node_ids = [n["id"] for n in old_nodes]
        print(f"📦 Archiving {len(node_ids)} low-utility nodes...")

        try:
            async with conn.transaction():
                # Перемещаем в архив
                await conn.execute(
                    """
                    INSERT INTO knowledge_nodes_archive
                    SELECT * FROM knowledge_nodes WHERE id = ANY($1)
                """,
                    node_ids,
                )

                # Удаляем из основной таблицы
                await conn.execute(
                    """
                    DELETE FROM knowledge_nodes WHERE id = ANY($1)
                """,
                    node_ids,
                )

            print(f"✅ Successfully archived {len(node_ids)} nodes.")
        except Exception as e:
            print(f"❌ Error during archiving: {e}")

        await conn.close()


if __name__ == "__main__":
    asyncio.run(archive_old_knowledge())
