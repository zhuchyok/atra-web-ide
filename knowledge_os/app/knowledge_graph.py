"""
[KNOWLEDGE OS] Knowledge Graph Engine.
Managing knowledge graph and links between nodes.
Part of the ATRA Singularity framework.
"""

import asyncio
import getpass
import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

# Third-party imports with fallback
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

logger = logging.getLogger(__name__)

USER_NAME = getpass.getuser()
# Priority: 1. env var, 2. local user (Mac), 3. fallback to admin (Server)
if USER_NAME == 'zhuchyok':
    DEFAULT_DB_URL = f'postgresql://{USER_NAME}@localhost:5432/knowledge_os'
else:
    DEFAULT_DB_URL = 'postgresql://admin:secret@localhost:5432/knowledge_os'

DB_URL = os.getenv('DATABASE_URL', DEFAULT_DB_URL)


class LinkType(Enum):
    """Типы связей между узлами знаний"""
    DEPENDS_ON = "depends_on"  # Зависит от
    CONTRADICTS = "contradicts"  # Противоречит
    ENHANCES = "enhances"  # Улучшает/расширяет
    RELATED_TO = "related_to"  # Связано с
    SUPERSEDES = "supersedes"  # Заменяет
    PART_OF = "part_of"  # Является частью


@dataclass
class KnowledgeLink:
    """Связь между узлами знаний"""
    source_id: str
    target_id: str
    link_type: LinkType
    strength: float = 1.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class KnowledgeGraph:
    """Класс для работы с графом знаний"""

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def create_link(
        self,
        source_id: str,
        target_id: str,
        link_type: LinkType,
        strength: float = 1.0,
        metadata: Optional[Dict] = None
    ) -> Optional[str]:
        """Создание связи между узлами знаний"""
        if source_id == target_id:
            logger.error("Cannot create link: source and target are the same")
            return None

        if not ASYNCPG_AVAILABLE:
            logger.error("❌ asyncpg is not installed. Operation aborted.")
            return None

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                link_id = await conn.fetchval("""
                    INSERT INTO knowledge_links
                    (source_node_id, target_node_id, link_type, strength, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (source_node_id, target_node_id, link_type)
                    DO UPDATE SET
                        strength = EXCLUDED.strength,
                        metadata = EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                """, source_id, target_id, link_type.value, strength, json.dumps(metadata or {}))

                logger.info("✅ Created link: %s --[%s]--> %s",
                            source_id, link_type.value, target_id)
                return str(link_id)
            finally:
                await conn.close()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error creating link: %s", exc)
            return None

    async def get_links(
        self,
        node_id: str,
        link_type: Optional[LinkType] = None,
        direction: str = "both"  # "outgoing", "incoming", "both"
    ) -> List[Dict]:
        """Получение всех связей узла"""
        if not ASYNCPG_AVAILABLE:
            return []

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                if direction == "outgoing":
                    query = """
                        SELECT * FROM knowledge_graph_view
                        WHERE source_node_id = $1
                    """
                    params = [node_id]
                elif direction == "incoming":
                    query = """
                        SELECT * FROM knowledge_graph_view
                        WHERE target_node_id = $1
                    """
                    params = [node_id]
                else:  # both
                    query = """
                        SELECT * FROM knowledge_graph_view
                        WHERE source_node_id = $1 OR target_node_id = $1
                    """
                    params = [node_id]

                if link_type:
                    query += " AND link_type = $2"
                    params.append(link_type.value)

                rows = await conn.fetch(query, *params)
                return [dict(row) for row in rows]
            finally:
                await conn.close()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error getting links: %s", exc)
            return []

    async def get_related_nodes(
        self,
        node_id: str,
        link_types: Optional[List[LinkType]] = None,
        max_depth: int = 2,
        min_strength: float = 0.5
    ) -> List[Dict]:
        """Получение связанных узлов (рекурсивно)"""
        if not ASYNCPG_AVAILABLE:
            return []

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                if link_types:
                    link_types_str = [lt.value for lt in link_types]
                else:
                    link_types_str = [
                        LinkType.DEPENDS_ON.value,
                        LinkType.ENHANCES.value,
                        LinkType.RELATED_TO.value
                    ]

                rows = await conn.fetch(
                    "SELECT * FROM get_related_nodes($1, $2, $3, $4)",
                    node_id,
                    link_types_str,
                    max_depth,
                    min_strength
                )
                return [dict(row) for row in rows]
            finally:
                await conn.close()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error getting related nodes: %s", exc)
            return []

    async def delete_link(
        self,
        source_id: str,
        target_id: str,
        link_type: LinkType
    ) -> bool:
        """Удаление связи"""
        if not ASYNCPG_AVAILABLE:
            return False

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                result = await conn.execute("""
                    DELETE FROM knowledge_links
                    WHERE source_node_id = $1
                      AND target_node_id = $2
                      AND link_type = $3
                """, source_id, target_id, link_type.value)

                return result == "DELETE 1"
            finally:
                await conn.close()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error deleting link: %s", exc)
            return False

    async def get_graph_stats(self) -> Dict[str, Any]:
        """Получение статистики графа"""
        if not ASYNCPG_AVAILABLE:
            return {}

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Общее количество связей
                total_links = await conn.fetchval("SELECT count(*) FROM knowledge_links")

                # Количество связей по типам
                links_by_type = await conn.fetch("""
                    SELECT link_type, count(*) as count
                    FROM knowledge_links
                    GROUP BY link_type
                    ORDER BY count DESC
                """)

                # Количество узлов со связями
                nodes_with_links = await conn.fetchval("""
                    SELECT count(DISTINCT source_node_id) + count(DISTINCT target_node_id)
                    FROM knowledge_links
                """)

                # Средняя сила связей
                avg_strength = await conn.fetchval("""
                    SELECT AVG(strength) FROM knowledge_links
                """) or 0.0

                return {
                    "total_links": total_links,
                    "links_by_type": {row["link_type"]: row["count"] for row in links_by_type},
                    "nodes_with_links": nodes_with_links,
                    "avg_strength": float(avg_strength)
                }
            finally:
                await conn.close()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error getting graph stats: %s", exc)
            return {}

    async def auto_detect_links(
        self,
        node_id: str,
        similarity_threshold: float = 0.8
    ) -> List[str]:
        """Автоматическое обнаружение связей на основе семантического сходства"""
        if not ASYNCPG_AVAILABLE:
            return []

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Получаем embedding текущего узла
                node = await conn.fetchrow("""
                    SELECT id, content, embedding, domain_id
                    FROM knowledge_nodes
                    WHERE id = $1
                """, node_id)

                if not node or not node["embedding"]:
                    return []

                # Ищем похожие узлы
                similar_nodes = await conn.fetch("""
                    SELECT
                        id,
                        content,
                        domain_id,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM knowledge_nodes
                    WHERE id != $2
                      AND embedding IS NOT NULL
                      AND (1 - (embedding <=> $1::vector)) >= $3
                    ORDER BY similarity DESC
                    LIMIT 10
                """, node["embedding"], node_id, similarity_threshold)

                created_links = []
                for similar in similar_nodes:
                    # Определяем тип связи на основе сходства и домена
                    if similar["domain_id"] == node["domain_id"]:
                        link_type = LinkType.RELATED_TO
                    else:
                        link_type = LinkType.ENHANCES

                    strength = float(similar["similarity"])

                    link_id = await self.create_link(
                        node_id,
                        str(similar["id"]),
                        link_type,
                        strength
                    )

                    if link_id:
                        created_links.append(link_id)

                logger.info("✅ Auto-detected %d links for node %s",
                            len(created_links), node_id)
                return created_links
            finally:
                await conn.close()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error auto-detecting links: %s", exc)
            return []


async def run_auto_link_detection():
    """Автоматическое обнаружение связей для всех узлов без связей"""
    if not ASYNCPG_AVAILABLE:
        logger.error("❌ asyncpg is not installed. Detection aborted.")
        return

    logger.info("🔗 Starting auto-link detection...")

    graph = KnowledgeGraph()
    conn = await asyncpg.connect(DB_URL)

    try:
        # Получаем узлы без связей
        nodes_without_links = await conn.fetch("""
            SELECT k.id
            FROM knowledge_nodes k
            LEFT JOIN knowledge_links kl ON k.id = kl.source_node_id OR k.id = kl.target_node_id
            WHERE kl.id IS NULL
            LIMIT 20
        """)

        logger.info("Found %d nodes without links", len(nodes_without_links))

        for node in nodes_without_links:
            await graph.auto_detect_links(str(node["id"]))
            await asyncio.sleep(0.5)  # Rate limiting

        logger.info("✅ Auto-link detection completed")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Auto-link detection error: %s", exc)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_auto_link_detection())
