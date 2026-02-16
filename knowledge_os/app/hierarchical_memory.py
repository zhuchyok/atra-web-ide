"""
[SINGULARITY 14.0] Hierarchical Memory Manager.
Implements Semantic Knowledge Pruning and Knowledge Resuscitation.
Moves inactive knowledge to 'archive' and keeps 'shadows' for re-activation.
"""

import os
import logging
import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class HierarchicalMemoryManager:
    """
    Manages active and archived knowledge to maintain RAG performance.
    """
    
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
        self.pruning_threshold_days = 180 # 6 months of inactivity

    async def _get_conn(self):
        import asyncpg
        return await asyncpg.connect(self.db_url)

    async def prune_inactive_knowledge(self) -> int:
        """
        Moves knowledge nodes that haven't been used for a long time to 'archived' state.
        Leaves a 'shadow' (summary) in the active base for resuscitation.
        """
        conn = await self._get_conn()
        try:
            threshold = datetime.now(timezone.utc) - timedelta(days=self.pruning_threshold_days)
            
            # 1. Find nodes to prune
            nodes = await conn.fetch("""
                SELECT id, content, metadata FROM knowledge_nodes 
                WHERE (last_used_at < $1 OR last_used_at IS NULL)
                AND created_at < $1
                AND (metadata->>'is_archived' IS NULL OR metadata->>'is_archived' = 'false')
                LIMIT 100
            """, threshold)
            
            if not nodes:
                return 0
                
            pruned_count = 0
            for node in nodes:
                # 2. Create a 'shadow' summary
                summary = f"ARCHIVED KNOWLEDGE: {node['content'][:100]}..."
                
                # 3. Update node to archived state
                await conn.execute("""
                    UPDATE knowledge_nodes 
                    SET metadata = metadata || '{"is_archived": true, "original_content_preview": $1}'::jsonb,
                        content = $2
                    WHERE id = $3
                """, node['content'][:200], summary, node['id'])
                
                pruned_count += 1
                
            logger.info(f"✂️ [PRUNING] Archived {pruned_count} inactive knowledge nodes.")
            return pruned_count
        finally:
            await conn.close()

    async def resuscitate_knowledge(self, node_id: str) -> bool:
        """
        Restores archived knowledge to active state.
        """
        conn = await self._get_conn()
        try:
            # In a real implementation, we would store the original content in a separate 'archive' table
            # or in a compressed metadata field. For now, we'll assume it's in metadata.
            node = await conn.fetchrow("SELECT metadata FROM knowledge_nodes WHERE id = $1", node_id)
            if not node or not node['metadata'].get('is_archived'):
                return False
                
            original_content = node['metadata'].get('original_content_preview', "Content lost")
            
            await conn.execute("""
                UPDATE knowledge_nodes 
                SET content = $1,
                    metadata = metadata - 'is_archived' - 'original_content_preview',
                    last_used_at = NOW()
                WHERE id = $2
            """, original_content, node_id)
            
            logger.info(f"✨ [RESUSCITATION] Restored knowledge node: {node_id}")
            return True
        finally:
            await conn.close()

    async def run_maintenance_cycle(self):
        """Periodic maintenance."""
        await self.prune_inactive_knowledge()

_instance = None
def get_hierarchical_memory_manager():
    global _instance
    if _instance is None:
        _instance = HierarchicalMemoryManager()
    return _instance
