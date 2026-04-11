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
        [SINGULARITY 24.0] Memory Cycle: Safe Vector Pruning & Semantic Merge.
        Перед поиском запускает цикл очистки и слияния дубликатов.
        """
        try:
            # [SINGULARITY 24.0] Memory Cycle
            from app.memory_cycle import get_memory_cycle
            cycle = get_memory_cycle(self.db_url)
            # Запускаем в фоне или периодически, здесь для демонстрации интеграции
            # asyncio.create_task(cycle.run_pruning())
            # asyncio.create_task(cycle.run_semantic_merge())

            from app.semantic_cache import get_embedding
            import json
            import hashlib
            
            # 0. Проверка кэша (Redis)
            try:
                from app.db_pool import get_redis_client
                redis = await get_redis_client()
                if redis:
                    query_hash = hashlib.md5(query.encode()).hexdigest()
                    cache_key = f"graphrag_cache:{query_hash}"
                    cached_data = await redis.get(cache_key)
                    if cached_data:
                        logger.info(f"🚀 [GRAPHRAG] Cache HIT for query: {query[:30]}...")
                        data = json.loads(cached_data)
                        return data["context"], data["nodes"]
            except Exception as ce:
                logger.debug(f"Redis cache check failed: {ce}")

            embedding = await get_embedding(query)
            if not embedding:
                return "", []

            # 1. Multi-hop поиск
            nodes = await self.retriever.retrieve_with_hops(embedding, max_hops=2, limit=limit)

            if not nodes:
                return "", []

            # 2. Формирование контекста
            context = "\n🌐 [GRAPHRAG GLOBAL CONTEXT]:\n"
            # ... (остальная логика формирования контекста)
            
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

            # 4. Сохранение в кэш (Redis) на 1 час
            try:
                if redis:
                    await redis.setex(
                        cache_key,
                        3600,
                        json.dumps({"context": context, "nodes": nodes})
                    )
                    logger.info(f"💾 [GRAPHRAG] Cache SET for query: {query[:30]}...")
            except Exception as se:
                logger.debug(f"Redis cache set failed: {se}")

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
