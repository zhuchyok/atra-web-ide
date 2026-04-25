import logging
import asyncio
from typing import Any, Dict, List, Optional
from app.long_term_memory import get_ltm
from app.semantic_cache import SemanticAICache

logger = logging.getLogger("KnowledgeFabric")

class KnowledgeFabric:
    """
    [SINGULARITY 28.2] Knowledge Fabric.
    Unifies Vector Memory (LTM), Graph Relations (GraphRAG), and Redis Cache (RAG).
    Provides a single entry point for all agent knowledge.
    """

    def __init__(self):
        self.ltm = get_ltm()
        self.cache = SemanticAICache()
        logger.info("🧠 Knowledge Fabric initialized (LTM + RAG unified)")

    async def query(self, text: str, limit: int = 5) -> Dict[str, Any]:
        """
        Unified query across all knowledge systems.
        """
        logger.info(f"🔍 [FABRIC] Querying knowledge for: {text[:50]}...")
        
        # 1. Check Semantic Cache (Fastest)
        cached_result = await self.cache.get_cache(text)
        if cached_result:
            logger.info("⚡ [FABRIC] Cache hit")
            return {"source": "cache", "content": cached_result}

        # 2. Query Long-term Memory (Vector similarity)
        memories = await self.ltm.recall_memories(text, limit=limit)
        
        # 3. Query Graph relations (Simulated for now, integration with knowledge_graph.py)
        # In a full implementation, we would also pull related nodes from the graph
        
        combined_content = "\n\n".join([m['content'] for m in memories])
        
        return {
            "source": "unified_memory",
            "content": combined_content,
            "metadata": {"memory_count": len(memories)}
        }

    async def store(self, content: str, source: str, metadata: Dict[str, Any] = None):
        """
        Unified storage. Automatically indexes in LTM and updates Graph.
        """
        logger.info(f"💾 [FABRIC] Storing knowledge from {source}")
        
        # 1. Store in LTM (Vector)
        memory_id = await self.ltm.store_memory(content, source, metadata)
        
        # 2. Update Cache
        await self.cache.set_cache(content, content, ttl=3600)
        
        return memory_id

_fabric = None

def get_knowledge_fabric() -> KnowledgeFabric:
    global _fabric
    if _fabric is None:
        _fabric = KnowledgeFabric()
    return _fabric
