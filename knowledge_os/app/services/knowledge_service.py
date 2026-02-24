import json
import logging
import os
from typing import Dict, List, Optional

import asyncpg

try:
    from db_pool import get_pool
    from semantic_cache import get_embedding
except ImportError:
    from app.db_pool import get_pool
    from app.semantic_cache import get_embedding

logger = logging.getLogger(__name__)


class KnowledgeService:
    """
    Микросервис для работы с базой знаний (RAG, эмбеддинги).
    Изолирует тяжелые операции с БД и векторами.
    """

    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")

    async def _get_knowledge_context(self, query: str, limit: int = 7) -> str:
        """Retrieve relevant knowledge nodes (RAG) - знания корпорации + AI Research (Singularity 10.0)."""
        try:
            # План «умнее быстрее» §1.1: Кэш контекста RAG (уровень 1)
            import hashlib

            query_hash = hashlib.md5(query.strip().lower().encode()).hexdigest()

            # Попытка получить из Redis если доступен
            try:
                from app.redis_manager import get_redis_manager

                rd = get_redis_manager()
                if rd:
                    cached = await rd.get_cache(f"rag_ctx:{query_hash}")
                    if cached:
                        logger.debug(f"⚡ [RAG CACHE HIT] {query[:50]}...")
                        return cached
            except Exception:
                pass

            embedding = await get_embedding(query)
            if not embedding:
                return ""
            pool = await get_pool()

            async with pool.acquire() as conn:
                # Поиск по основным доменам с приоритетом недавних и часто используемых
                rows = await conn.fetch(
                    """
                    SELECT content, metadata, (1 - (embedding <=> $1::vector)) as similarity
                    FROM knowledge_nodes
                    WHERE embedding IS NOT NULL
                    AND (
                        domain_id = (SELECT id FROM domains WHERE name = 'AI Research' LIMIT 1)
                        OR domain_id = (SELECT id FROM domains WHERE name = 'victoria_tasks' LIMIT 1)
                        OR domain_id = (SELECT id FROM domains WHERE name = 'project_files' LIMIT 1)
                        OR metadata->>'source' = 'external_docs_indexer'
                        OR metadata->>'source' = 'indexing_daemon'
                    )
                    AND confidence_score >= 0.3
                    ORDER BY similarity DESC, usage_count DESC NULLS LAST, created_at DESC
                    LIMIT $2
                """,
                    embedding,
                    limit,
                )

                if not rows:
                    return ""

                context = "\n📚 [KNOWLEDGE CONTEXT]:\n"
                for row in rows:
                    if row["similarity"] >= 0.6:
                        meta = row["metadata"] or {}
                        source = meta.get("source", "unknown")
                        file_path = meta.get("file_path", "N/A")

                        if source == "external_docs_indexer":
                            context += f"\n[AI RESEARCH: {file_path}] (релевантность: {row['similarity']:.2f}):\n"
                        elif source == "indexing_daemon":
                            context += f"\n[PROJECT FILE: {file_path}] (релевантность: {row['similarity']:.2f}):\n"
                        else:
                            context += f"\n[КОРПОРАЦИЯ] (релевантность: {row['similarity']:.2f}):\n"

                        context += f"{row['content'][:1000]}\n"

                # Сохраняем в кэш на 5 минут
                try:
                    if rd:
                        await rd.set_cache(f"rag_ctx:{query_hash}", context, ttl=300)
                except Exception:
                    pass

                return context
        except Exception as exc:
            logger.error(f"Knowledge retrieval error: {exc}")
            return ""

    async def save_insight(self, content: str, expert_name: str, metadata: Dict = None):
        """Сохраняет новый инсайт в базу знаний."""
        embedding = await get_embedding(content[:1000])

        # Сингулярность 10.0: Если эмбеддинг не получен, используем нулевой вектор нужной размерности
        if not embedding:
            logger.warning(
                "⚠️ [KNOWLEDGE SERVICE] Не удалось получить эмбеддинг для инсайта, используем нулевой вектор"
            )
            embedding = [0.0] * 768

        # Преобразуем список в строку формата '[1.2, 3.4, ...]' для pgvector, если это список
        if isinstance(embedding, list):
            # Проверка размерности (pgvector требует строгого соответствия)
            if len(embedding) != 768:
                logger.warning(
                    f"⚠️ [KNOWLEDGE SERVICE] Размерность эмбеддинга {len(embedding)} != 768. Корректируем."
                )
                if len(embedding) > 768:
                    embedding = embedding[:768]
                else:
                    embedding = embedding + [0.0] * (768 - len(embedding))
            embedding_str = "[" + ",".join(map(str, embedding)) + "]"
        else:
            embedding_str = embedding

        pool = await get_pool()
        async with pool.acquire() as conn:
            # Сингулярность 10.0: Гарантируем, что metadata — это JSON-строка для PostgreSQL
            metadata_json = json.dumps(metadata or {})
            await conn.execute(
                """
                INSERT INTO knowledge_nodes (content, domain_id, confidence_score, embedding, is_verified, metadata)
                VALUES ($1, (SELECT id FROM domains WHERE name = 'victoria_tasks' LIMIT 1), 0.9, $2, TRUE, $3::jsonb)
            """,
                content,
                embedding_str,
                metadata_json,
            )
            logger.info(f"📚 [KNOWLEDGE SERVICE] Сохранен инсайт от {expert_name}")


knowledge_service = KnowledgeService()
