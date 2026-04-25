import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

try:
    from app.db_pool import get_pool
    from app.semantic_cache import get_embedding
except ImportError:
    from db_pool import get_pool
    from semantic_cache import get_embedding

logger = logging.getLogger("LongTermMemory")

class LongTermMemory:
    """
    [SINGULARITY 28.0] Persistent Long-term Memory.
    Saves context, decisions, and insights between sessions using Vector DB and Graph relations.
    """
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")

    async def store_memory(self, content: str, source: str, metadata: Dict[str, Any] = None):
        """Store a memory node and generate its embedding."""
        embedding = await get_embedding(content[:2000])
        if not embedding:
            embedding = [0.0] * 768 # Fallback
            
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"
        pool = await get_pool()
        
        async with pool.acquire() as conn:
            memory_id = await conn.fetchval(
                """
                INSERT INTO knowledge_nodes (content, domain_id, confidence_score, embedding, is_verified, metadata)
                VALUES ($1, (SELECT id FROM domains WHERE name = 'AI Research' LIMIT 1), 1.0, $2, TRUE, $3::jsonb)
                RETURNING id
                """,
                content,
                embedding_str,
                json.dumps({**(metadata or {}), "source": source, "type": "long_term_memory"})
            )
            logger.info(f"💾 [LTM] Stored memory from {source}: {memory_id}")
            return memory_id

    async def recall_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Recall relevant memories using vector similarity."""
        embedding = await get_embedding(query)
        if not embedding:
            return []
            
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT content, metadata, (1 - (embedding <=> $1::vector)) as similarity
                FROM knowledge_nodes
                WHERE metadata->>'type' = 'long_term_memory'
                AND (1 - (embedding <=> $1::vector)) > 0.7
                ORDER BY similarity DESC
                LIMIT $2
                """,
                embedding,
                limit
            )
            return [dict(r) for r in rows]

    async def link_memories(self, source_id: Any, target_id: Any, relation: str):
        """Create a graph edge between two memory nodes."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO knowledge_edges (source_id, target_id, relation_type) VALUES ($1, $2, $3)",
                source_id, target_id, relation
            )
            logger.info(f"🔗 [LTM] Linked memories {source_id} -> {target_id} ({relation})")

_ltm = None

def get_ltm() -> LongTermMemory:
    global _ltm
    if _ltm is None:
        _ltm = LongTermMemory()
    return _ltm

def get_long_term_memory_manager() -> LongTermMemory:
    """Alias for backwards compatibility."""
    return get_ltm()
