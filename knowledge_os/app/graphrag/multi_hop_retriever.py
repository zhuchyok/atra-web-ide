import logging
import asyncio
from typing import List, Dict, Any, Optional
import json

logger = logging.getLogger(__name__)

class MultiHopRetriever:
    """
    Реализует многошаговый поиск по графу знаний (Multi-Hop Reasoning).
    Находит не только похожие узлы, но и логически связанные цепочки.
    """
    def __init__(self, db_url: str):
        self.db_url = db_url

    async def retrieve_with_hops(self, query_embedding: List[float], max_hops: int = 2, limit: int = 5) -> List[Dict[str, Any]]:
        """
        1. Находит 'seed' узлы через векторный поиск.
        2. Рекурсивно обходит связи (hops).
        3. Ранжирует цепочки по релевантности.
        """
        import asyncpg
        try:
            conn = await asyncpg.connect(self.db_url)
            
            # Шаг 1: Seed nodes (векторный поиск)
            seeds = await conn.fetch("""
                SELECT id, content, confidence_score, domain_id,
                       (1 - (embedding <=> $1::vector)) as similarity
                FROM knowledge_nodes
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """, query_embedding, limit)

            if not seeds:
                await conn.close()
                return []

            seed_ids = [s['id'] for s in seeds]
            all_results = {str(s['id']): dict(s) for s in seeds}

            # Шаг 2: Multi-hop traversal (через рекурсивный CTE)
            hops_data = await conn.fetch("""
                WITH RECURSIVE graph_path AS (
                    -- Начальные узлы
                    SELECT source_node_id, target_node_id, link_type, strength, 1 as hop_count
                    FROM knowledge_links
                    WHERE source_node_id = ANY($1::uuid[])
                    
                    UNION ALL
                    
                    -- Рекурсивный переход
                    SELECT l.source_node_id, l.target_node_id, l.link_type, l.strength, gp.hop_count + 1
                    FROM knowledge_links l
                    INNER JOIN graph_path gp ON l.source_node_id = gp.target_node_id
                    WHERE gp.hop_count < $2
                )
                SELECT gp.*, kn.content, kn.domain_id
                FROM graph_path gp
                JOIN knowledge_nodes kn ON gp.target_node_id = kn.id
                ORDER BY gp.strength DESC, gp.hop_count ASC
                LIMIT 20
            """, seed_ids, max_hops)

            # Шаг 3: Сборка контекста
            for h in hops_data:
                tid = str(h['target_node_id'])
                if tid not in all_results:
                    all_results[tid] = {
                        "id": h['target_node_id'],
                        "content": h['content'],
                        "similarity": h['strength'] * 0.8, # Пенальти за хоп
                        "is_hop": True,
                        "hop_source": str(h['source_node_id'])
                    }

            await conn.close()
            return list(all_results.values())

        except Exception as e:
            logger.error(f"Multi-hop retrieval failed: {e}")
            return []

_retriever = None
def get_multi_hop_retriever(db_url: str):
    global _retriever
    if _retriever is None:
        _retriever = MultiHopRetriever(db_url)
    return _retriever
