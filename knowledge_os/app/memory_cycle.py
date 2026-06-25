import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import asyncpg
from app.semantic_cache import get_embedding

logger = logging.getLogger(__name__)


class MemoryCycle:
    """
    Memory Cycle (Singularity 24.0).
    Реализует Safe Vector Pruning: Soft Delete и Semantic Merge.
    """

    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.getenv(
            "DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os"
        )

    async def _bump_freshness_version(self):
        """Invalidate freshness generation for downstream caches."""
        try:
            from app.redis_manager import get_redis_manager

            redis_manager = get_redis_manager()
            client = await redis_manager.get_client()
            if client:
                await client.incr("knowledge:freshness:generation")
                await client.set(
                    "knowledge:freshness:updated_at", datetime.now(timezone.utc).isoformat()
                )
        except Exception as e:
            logger.debug("Freshness generation bump failed: %s", e)

    async def run_pruning(self) -> int:
        """Запускает Soft Delete процедуру."""
        conn = await asyncpg.connect(self.db_url)
        try:
            count = await conn.fetchval("SELECT prune_knowledge_nodes()")
            logger.info(f"♻️ [MEMORY CYCLE] Soft Delete: {count} nodes moved to archive.")
            if count and count > 0:
                await self._bump_freshness_version()
            return count
        finally:
            await conn.close()

    async def run_semantic_merge(self, similarity_threshold: float = 0.95):
        """
        Ищет дубликаты и объединяет их.
        Узлы с is_verified = true, memory_crystals и domain_summary НЕПРИКОСНОВЕННЫ.
        """
        conn = await asyncpg.connect(self.db_url)
        try:
            # Ищем пары дубликатов через векторное сходство
            # Исключаем неприкосновенные узлы из удаления (но они могут быть целью слияния)
            query = """
                SELECT n1.id as id1, n2.id as id2, n1.content as content1, n2.content as content2
                FROM knowledge_nodes n1
                JOIN knowledge_nodes n2 ON n1.id < n2.id
                WHERE (n1.embedding <=> n2.embedding) < $1
                  AND n2.is_verified = FALSE
                  AND (n2.metadata->>'type' IS NULL OR n2.metadata->>'type' NOT IN ('memory_crystal', 'domain_summary'))
                LIMIT 100
            """
            # similarity = 1 - distance. distance < 0.05 means similarity > 0.95
            distance_threshold = 1.0 - similarity_threshold
            duplicates = await conn.fetch(query, distance_threshold)

            merged_count = 0
            for dup in duplicates:
                # Объединяем n2 в n1
                # 1. Обновляем usage_count и metadata n1
                await conn.execute(
                    """
                    UPDATE knowledge_nodes
                    SET usage_count = usage_count + (SELECT usage_count FROM knowledge_nodes WHERE id = $2),
                        metadata = metadata || (SELECT metadata FROM knowledge_nodes WHERE id = $2),
                        updated_at = NOW()
                    WHERE id = $1
                """,
                    dup["id1"],
                    dup["id2"],
                )

                # 2. Перенаправляем связи (если есть таблица knowledge_links)
                # Проверяем существование таблицы knowledge_links
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'knowledge_links'
                    )
                """)
                if table_exists:
                    await conn.execute(
                        "UPDATE knowledge_links SET source_id = $1 WHERE source_id = $2",
                        dup["id1"],
                        dup["id2"],
                    )
                    await conn.execute(
                        "UPDATE knowledge_links SET target_id = $1 WHERE target_id = $2",
                        dup["id1"],
                        dup["id2"],
                    )

                # 3. Удаляем дубликат
                await conn.execute("DELETE FROM knowledge_nodes WHERE id = $1", dup["id2"])
                merged_count += 1
                logger.info(
                    f"🤝 [MEMORY CYCLE] Semantic Merge: Merged {dup['id2']} into {dup['id1']}"
                )

            if merged_count > 0:
                logger.info(
                    f"♻️ [MEMORY CYCLE] Semantic Merge complete: {merged_count} duplicates merged."
                )
                await self._bump_freshness_version()
            return merged_count
        finally:
            await conn.close()


_memory_cycle = None


def get_memory_cycle(db_url: str = None) -> MemoryCycle:
    global _memory_cycle
    if _memory_cycle is None:
        _memory_cycle = MemoryCycle(db_url)
    return _memory_cycle
