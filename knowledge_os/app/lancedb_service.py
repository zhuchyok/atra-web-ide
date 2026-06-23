# /Users/bikos/Documents/atra-web-ide/knowledge_os/app/lancedb_service.py
"""
[SINGULARITY 31.0] LanceDB Service for ultra-fast vector search.
Provides zero-latency RAG and knowledge retrieval.
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import lancedb
import pyarrow as pa

logger = logging.getLogger(__name__)

LANCE_DB_PATH = os.getenv("LANCE_DB_PATH", "/app/data/lancedb")
TABLE_NAME = "knowledge_nodes"
EMBEDDING_DIM = 768  # nomic-embed-text


class LanceDBService:
    _instance = None
    _db = None
    _table = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LanceDBService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._db is None:
            os.makedirs(LANCE_DB_PATH, exist_ok=True)
            self._db = lancedb.connect(LANCE_DB_PATH)
            self._init_table()

    def _init_table(self):
        """Initializes the table if it doesn't exist."""
        try:
            if TABLE_NAME in self._db.table_names():
                self._table = self._db.open_table(TABLE_NAME)
            else:
                # Define schema
                schema = pa.schema(
                    [
                        pa.field("id", pa.string()),
                        pa.field("vector", pa.list_(pa.float32(), EMBEDDING_DIM)),
                        pa.field("content", pa.string()),
                        pa.field("metadata", pa.string()),  # JSON string
                        pa.field("confidence_score", pa.float32()),
                        pa.field("created_at", pa.string()),
                    ]
                )
                self._table = self._db.create_table(TABLE_NAME, schema=schema)
                logger.info(f"✅ [LANCEDB] Table '{TABLE_NAME}' created.")
        except Exception as e:
            logger.error(f"❌ [LANCEDB] Initialization error: {e}")

    async def search(
        self, embedding: List[float], limit: int = 5, filter: Optional[str] = None
    ) -> List[Dict]:
        """Performs vector search."""
        if not self._table:
            return []

        try:
            query = self._table.search(embedding).limit(limit)
            if filter:
                query = query.where(filter)

            results = query.to_list()

            # Convert to standard format
            formatted = []
            for r in results:
                import json

                try:
                    meta = json.loads(r["metadata"])
                except:
                    meta = {}

                formatted.append(
                    {
                        "id": r["id"],
                        "content": r["content"],
                        "metadata": meta,
                        "confidence_score": r["confidence_score"],
                        "similarity": 1.0
                        - r["_distance"],  # LanceDB returns L2 distance by default
                        "created_at": r["created_at"],
                    }
                )
            return formatted
        except Exception as e:
            logger.error(f"❌ [LANCEDB] Search error: {e}")
            return []

    async def upsert_batch(self, nodes: List[Dict]):
        """Upserts a batch of nodes."""
        if not self._table:
            return

        try:
            import json

            data = []
            for n in nodes:
                data.append(
                    {
                        "id": str(n["id"]),
                        "vector": n["vector"],
                        "content": n["content"],
                        "metadata": json.dumps(n.get("metadata", {})),
                        "confidence_score": float(n.get("confidence_score", 0.0)),
                        "created_at": n.get("created_at", datetime.now().isoformat()),
                    }
                )

            # Append mode prevents clobbering previous vectors on every batch.
            self._table.add(data)
            logger.info(f"💾 [LANCEDB] Upserted {len(data)} nodes.")
        except Exception as e:
            logger.error(f"❌ [LANCEDB] Upsert error: {e}")


def get_lancedb_service() -> LanceDBService:
    return LanceDBService()
