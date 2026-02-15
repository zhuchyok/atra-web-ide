import logging
import asyncio
from typing import List, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

class CommunityDetector:
    """
    Группирует узлы знаний в иерархические сообщества.
    Использует упрощенный алгоритм Label Propagation для работы в реальном времени.
    """
    def __init__(self, db_url: str):
        self.db_url = db_url

    async def detect_communities(self) -> Dict[str, List[str]]:
        """Обнаруживает сообщества в графе знаний."""
        import asyncpg
        try:
            conn = await asyncpg.connect(self.db_url)
            # 1. Загружаем все связи
            links = await conn.fetch("SELECT source_node_id, target_node_id FROM knowledge_links")
            
            # 2. Строим граф смежности
            adj = {}
            nodes = set()
            for l in links:
                s, t = str(l['source_node_id']), str(l['target_node_id'])
                nodes.add(s)
                nodes.add(t)
                if s not in adj: adj[s] = []
                if t not in adj: adj[t] = []
                adj[s].append(t)
                adj[t].append(s)

            # 3. Label Propagation
            labels = {node: node for node in nodes}
            for _ in range(5): # 5 итераций достаточно для сходимости небольших групп
                for node in nodes:
                    if node in adj:
                        neighbor_labels = [labels[neighbor] for neighbor in adj[node]]
                        if neighbor_labels:
                            # Выбираем самую частую метку среди соседей
                            labels[node] = max(set(neighbor_labels), key=neighbor_labels.count)

            # 4. Группируем по меткам
            communities = {}
            for node, label in labels.items():
                if label not in communities: communities[label] = []
                communities[label].append(node)

            # 5. Сохраняем community_id в метаданные узлов
            for comm_id, node_ids in communities.items():
                await conn.execute("""
                    UPDATE knowledge_nodes 
                    SET metadata = metadata || jsonb_build_object('community_id', $1)
                    WHERE id = ANY($2::uuid[])
                """, comm_id, [asyncio.get_event_loop().run_in_executor(None, lambda x: x, nid) for nid in node_ids]) # Упрощенно

            await conn.close()
            logger.info(f"✅ Обнаружено {len(communities)} сообществ в графе знаний")
            return communities

        except Exception as e:
            logger.error(f"Community detection failed: {e}")
            return {}

_detector = None
def get_community_detector(db_url: str):
    global _detector
    if _detector is None:
        _detector = CommunityDetector(db_url)
    return _detector
