import logging
import os
from typing import Any, Dict, List, Optional

from .community_detector import get_community_detector
from .entity_extractor import get_entity_extractor
from .multi_hop_retriever import get_multi_hop_retriever

logger = logging.getLogger(__name__)


class GraphRAGService:
    """
    Единый сервис GraphRAG (Singularity 10.0).
    Объединяет векторный поиск, экстракцию сущностей и многошаговое рассуждение.
    """

    def __init__(self):
        self.db_url = os.getenv(
            "DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os"
        )
        self.extractor = get_entity_extractor()
        self.detector = get_community_detector(self.db_url)
        self.retriever = get_multi_hop_retriever(self.db_url)

    async def retrieve_graph_context(self, query: str, limit: int = 8) -> tuple[str, list]:
        """
        Выполняет полный цикл GraphRAG поиска:
        1. Получает embedding запроса.
        2. Извлекает сущности из запроса.
        3. Выполняет multi-hop поиск по графу.
        4. Формирует структурированный контекст.
        Returns: (context_string, nodes_list)
        """
        try:
            from app.semantic_cache import get_embedding

            embedding = await get_embedding(query)
            if not embedding:
                return "", []

            # 1. Multi-hop поиск
            nodes = await self.retriever.retrieve_with_hops(embedding, max_hops=2, limit=limit)

            if not nodes:
                return "", []

            # 2. Формирование контекста
            context = "\n🌐 [GRAPHRAG GLOBAL CONTEXT]:\n"

            # Группируем результаты: прямые и связанные (hops)
            direct_nodes = [n for n in nodes if not n.get("is_hop")]
            hop_nodes = [n for n in nodes if n.get("is_hop")]

            context += "\n--- КЛЮЧЕВЫЕ ЗНАНИЯ (Direct Match) ---\n"
            for n in direct_nodes[:5]:
                context += f"- {n['content'][:800]}\n"

            if hop_nodes:
                context += "\n--- ЛОГИЧЕСКИ СВЯЗАННЫЕ ЦЕПОЧКИ (Multi-Hop) ---\n"
                for n in hop_nodes[:5]:
                    context += (
                        f"- [Связь через {n.get('hop_source', '...')[:8]}]: {n['content'][:600]}\n"
                    )

            # 3. Извлечение сущностей из запроса для подсветки (опционально)
            entities = await self.extractor.extract_entities(query)
            if entities:
                context += f"\n🔍 ОБНАРУЖЕННЫЕ СУЩНОСТИ: {', '.join([e.name for e in entities])}\n"

            return context, nodes

        except Exception as e:
            logger.error(f"GraphRAG retrieval error: {e}")
            return "", []


_service = None


def get_graphrag_service():
    global _service
    if _service is None:
        _service = GraphRAGService()
    return _service
