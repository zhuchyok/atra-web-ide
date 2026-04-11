import asyncio
import logging
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class CommunityDetector:
    """
    Группирует узлы знаний в иерархические сообщества.
    Использует упрощенный алгоритм Label Propagation для работы в реальном времени.
    """

    def __init__(self, db_url: str):
        self.db_url = db_url

    async def detect_communities(self, iterations: int = 10) -> Dict[str, List[str]]:
        """
        [SINGULARITY 23.8] Optimized Community Detection:
        Использует централизованный пул и пакетные операции.
        """
        import uuid
        from app.db_pool import get_pool

        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                # 1. Загружаем все связи с весами
                links = await conn.fetch(
                    "SELECT source_node_id, target_node_id, strength FROM knowledge_links WHERE strength > 0.2"
                )

                # 2. Строим взвешенный граф смежности
                adj = {}
                nodes = set()
                for l in links:
                    s, t = str(l["source_node_id"]), str(l["target_node_id"])
                    w = float(l["strength"])
                    nodes.add(s)
                    nodes.add(t)
                    if s not in adj: adj[s] = []
                    if t not in adj: adj[t] = []
                    adj[s].append((t, w))
                    adj[t].append((s, w))

                if not nodes:
                    return {}

                # 3. Улучшенный Label Propagation (Weighted)
                labels = {node: node for node in nodes}
                node_list = list(nodes)
                
                for _ in range(iterations):
                    changed = False
                    np.random.shuffle(node_list)

                    for node in node_list:
                        if node in adj:
                            label_weights = {}
                            for neighbor, weight in adj[node]:
                                l = labels[neighbor]
                                label_weights[l] = label_weights.get(l, 0) + weight

                            if label_weights:
                                new_label = max(label_weights, key=label_weights.get)
                                if labels[node] != new_label:
                                    labels[node] = new_label
                                    changed = True
                    if not changed:
                        break

                # 4. Группируем по меткам (Уровень 1)
                communities = {}
                for node, label in labels.items():
                    if label not in communities: communities[label] = []
                    communities[label].append(node)

                # 5. Иерархическая обработка
                hierarchical_map = {}
                for comm_id, node_ids in communities.items():
                    if len(node_ids) < 5:
                        external_weights = {}
                        for node in node_ids:
                            for neighbor, weight in adj.get(node, []):
                                neighbor_label = labels[neighbor]
                                if neighbor_label != comm_id:
                                    external_weights[neighbor_label] = external_weights.get(neighbor_label, 0) + weight

                        hierarchical_map[comm_id] = max(external_weights, key=external_weights.get) if external_weights else comm_id
                    else:
                        hierarchical_map[comm_id] = comm_id

                # 6. Сохраняем в БД пакетно
                async with conn.transaction():
                    for comm_id, node_ids in communities.items():
                        parent_id = hierarchical_map[comm_id]
                        uuid_list = [uuid.UUID(nid) for nid in node_ids]
                        await conn.execute(
                            """
                            UPDATE knowledge_nodes
                            SET metadata = metadata || jsonb_build_object(
                                'community_id', $1::text,
                                'parent_community_id', $2::text,
                                'community_updated_at', NOW()
                            )
                            WHERE id = ANY($3::uuid[])
                        """,
                            comm_id, parent_id, uuid_list,
                        )

                logger.info(f"✅ Обнаружено {len(communities)} сообществ. Иерархия выстроена.")
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
