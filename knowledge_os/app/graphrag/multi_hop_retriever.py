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
        [SINGULARITY 10.0+] Параллельный многошаговый поиск.
        1. Находит 'seed' узлы через векторный поиск.
        2. Параллельно обходит связи (hops) и оценивает их релевантность запросу.
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

            # Шаг 2: Параллельный обход и Query-Aware Scoring
            # Мы используем asyncio.gather для параллельного выполнения запросов по разным путям или типам связей
            # В данном случае оптимизируем через разделение на 'сильные' и 'семантические' пути
            
            async def fetch_hops(ids, depth):
                return await conn.fetch("""
                    WITH RECURSIVE graph_path AS (
                        SELECT source_node_id, target_node_id, link_type, strength, 1 as hop_count
                        FROM knowledge_links
                        WHERE source_node_id = ANY($1::uuid[])
                        
                        UNION ALL
                        
                        SELECT l.source_node_id, l.target_node_id, l.link_type, l.strength, gp.hop_count + 1
                        FROM knowledge_links l
                        INNER JOIN graph_path gp ON l.source_node_id = gp.target_node_id
                        WHERE gp.hop_count < $2 AND l.strength > 0.5
                    )
                    SELECT gp.*, kn.content, kn.domain_id,
                           (1 - (kn.embedding <=> $3::vector)) as node_similarity
                    FROM graph_path gp
                    JOIN knowledge_nodes kn ON gp.target_node_id = kn.id
                    ORDER BY gp.strength DESC, gp.hop_count ASC
                    LIMIT 30
                """, ids, depth, query_embedding)

            # Параллельно запрашиваем разные уровни графа или разные наборы семян
            hop_tasks = [
                fetch_hops(seed_ids[:2], max_hops), # Самые релевантные семена - глубже
                fetch_hops(seed_ids[2:], min(max_hops, 1)) # Остальные - только 1 шаг
            ]
            
            hop_results = await asyncio.gather(*hop_tasks)
            
            # Шаг 3: Сборка и Query-Aware Scoring
            for hops_data in hop_results:
                for h in hops_data:
                    tid = str(h['target_node_id'])
                    # Query-Aware Score: комбинация силы связи, близости узла к запросу и глубины
                    path_score = (h['strength'] * 0.4) + (h['node_similarity'] * 0.5) - (h['hop_count'] * 0.1)
                    
                    if tid not in all_results or path_score > all_results[tid].get('similarity', 0):
                        all_results[tid] = {
                            "id": h['target_node_id'],
                            "content": h['content'],
                            "similarity": path_score,
                            "is_hop": True,
                            "hop_count": h['hop_count'],
                            "hop_source": str(h['source_node_id']),
                            "link_type": h['link_type']
                        }

            await conn.close()
            # Сортируем по итоговому score
            sorted_results = sorted(all_results.values(), key=lambda x: x['similarity'], reverse=True)
            return sorted_results[:limit * 2]

        except Exception as e:
            logger.error(f"Multi-hop retrieval failed: {e}")
            return []

_retriever = None
def get_multi_hop_retriever(db_url: str):
    global _retriever
    if _retriever is None:
        _retriever = MultiHopRetriever(db_url)
    return _retriever
