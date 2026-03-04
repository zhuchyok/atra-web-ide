import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("vector_cache")


class LocalVectorCache:
    """
    [SINGULARITY 24.0] Local Vector Cache in RAM.
    Provides millisecond-level similarity search for knowledge nodes.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LocalVectorCache, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "initialized"):
            return
        self.embeddings = None  # NumPy array (N, dim)
        self.metadata = []  # List of dicts
        self.contents = []  # List of strings
        self.last_sync = None
        self.initialized = True
        self._lock = asyncio.Lock()

    async def sync_from_db(self, pool):
        """Loads all relevant knowledge nodes from DB into RAM."""
        async with self._lock:
            try:
                logger.info("🔄 [VECTOR CACHE] Syncing knowledge nodes to RAM...")
                async with pool.acquire() as conn:
                    rows = await conn.fetch("""
                        SELECT content, metadata, embedding
                        FROM knowledge_nodes
                        WHERE embedding IS NOT NULL
                        AND confidence_score >= 0.3
                        AND (
                            domain_id IN (SELECT id FROM domains WHERE name IN ('AI Research', 'victoria_tasks'))
                            OR metadata->>'source' = 'external_docs_indexer'
                            OR source_ref = 'autonomous_worker'
                            OR metadata->>'type' = 'corporate_standard'
                        )
                    """)

                    if not rows:
                        logger.warning("⚠️ [VECTOR CACHE] No nodes found in DB.")
                        return

                    new_embeddings = []
                    new_metadata = []
                    new_contents = []

                    for row in rows:
                        emb_str = row["embedding"]
                        if isinstance(emb_str, str):
                            # pgvector returns string representation like '[1,2,3]'
                            emb = np.fromstring(emb_str.strip("[]"), sep=",")
                        else:
                            emb = np.array(emb_str)

                        new_embeddings.append(emb)
                        new_metadata.append(row["metadata"] or {})
                        new_contents.append(row["content"])

                    self.embeddings = np.array(new_embeddings)
                    self.metadata = new_metadata
                    self.contents = new_contents
                    self.last_sync = datetime.now()

                    logger.info(f"✅ [VECTOR CACHE] Cached {len(self.contents)} nodes in RAM.")

            except Exception as e:
                logger.error(f"❌ [VECTOR CACHE] Sync failed: {e}")

    async def search(
        self, query_embedding: List[float], limit: int = 8, threshold: float = 0.5
    ) -> List[Dict]:
        """Performs fast cosine similarity search in RAM."""
        if self.embeddings is None or len(self.embeddings) == 0:
            return []

        # Vectorized cosine similarity
        q = np.array(query_embedding)

        # Normalize vectors for cosine similarity (dot product of normalized vectors)
        norm_q = np.linalg.norm(q)
        if norm_q == 0:
            return []

        # We assume cached embeddings might not be normalized
        norms = np.linalg.norm(self.embeddings, axis=1)
        # Avoid division by zero
        norms[norms == 0] = 1.0

        similarities = np.dot(self.embeddings, q) / (norms * norm_q)

        # Filter by threshold and get top K
        indices = np.where(similarities >= threshold)[0]
        if len(indices) == 0:
            return []

        # Sort by similarity descending
        top_indices = indices[np.argsort(similarities[indices])[::-1][:limit]]

        results = []
        for idx in top_indices:
            results.append(
                {
                    "content": self.contents[idx],
                    "metadata": self.metadata[idx],
                    "similarity": float(similarities[idx]),
                }
            )

        return results


# Singleton instance
vector_cache = LocalVectorCache()


async def get_vector_cache():
    return vector_cache
