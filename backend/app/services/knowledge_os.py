"""
Knowledge OS Client
Интеграция с базой знаний Singularity
"""
import asyncpg
from typing import Optional, List
import logging

from fastapi import Request
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class KnowledgeOSClient:
    """Клиент для Knowledge OS Database"""

    def __init__(
        self,
        database_url: Optional[str] = None,
        pool: Optional[asyncpg.Pool] = None,
    ):
        self.database_url = database_url or settings.database_url
        self._pool: Optional[asyncpg.Pool] = pool
        self._own_pool = pool is None

    async def connect(self):
        """Создать пул соединений (только при lazy init)"""
        if self._pool is not None:
            return
        try:
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=settings.database_pool_min_size,
                max_size=settings.database_pool_max_size,
            )
            logger.info("✅ Knowledge OS DB connected")
        except Exception as e:
            logger.error(f"❌ Knowledge OS DB connection failed: {e}")
            raise

    async def disconnect(self):
        """Закрыть пул соединений (только если мы его создали)"""
        if self._pool and self._own_pool:
            await self._pool.close()
        self._pool = None
    
    async def get_experts(self) -> List[dict]:
        """Получить список всех экспертов"""
        if self._pool is None:
            await self.connect()
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    id,
                    name,
                    role,
                    system_prompt,
                    created_at
                FROM experts
                ORDER BY name
            """)
            return [dict(row) for row in rows]
    
    async def get_expert(self, expert_id: str) -> Optional[dict]:
        """Получить эксперта по ID"""
        if self._pool is None:
            await self.connect()
        
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT 
                    id,
                    name,
                    role,
                    system_prompt,
                    created_at
                FROM experts
                WHERE id = $1
            """, expert_id)
            return dict(row) if row else None
    
    # Veronica/Victoria: Latin в коде → Cyrillic в БД (все регистры)
    _EXPERT_NAME_TO_DB = {
        "Veronica": "Вероника", "veronica": "Вероника", "VERONICA": "Вероника",
        "Victoria": "Виктория", "victoria": "Виктория", "VICTORIA": "Виктория",
    }

    async def get_expert_by_name(self, name: str) -> Optional[dict]:
        """Получить эксперта по имени. Veronica→Вероника, Victoria→Виктория."""
        if self._pool is None:
            await self.connect()
        n = (name or "").strip()
        resolved = self._EXPERT_NAME_TO_DB.get(n, name)
        async with self._pool.acquire() as conn:
            for candidate in [resolved, name]:
                if not candidate:
                    continue
                row = await conn.fetchrow("""
                    SELECT id, name, role, system_prompt, created_at
                    FROM experts WHERE name = $1
                """, candidate)
                if row:
                    return dict(row)
            return None
    
    async def get_domains(self) -> List[dict]:
        """Получить список доменов"""
        if self._pool is None:
            await self.connect()
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    id,
                    name,
                    description,
                    created_at
                FROM domains
                ORDER BY name
            """)
            return [dict(row) for row in rows]
    
    async def search_knowledge_by_vector(
        self,
        embedding: List[float],
        limit: int = 1,
        threshold: float = 0.75,
    ) -> List[dict]:
        """
        Векторный поиск по knowledge_nodes (pgvector).
        Возвращает чанки с similarity >= threshold.
        """
        if self._pool is None:
            await self.connect()
        # PostgreSQL pgvector: <=> это оператор расстояния (1 - distance = similarity)
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT content, metadata, (1 - (embedding <=> $1::vector)) AS similarity
                    FROM knowledge_nodes
                    WHERE embedding IS NOT NULL AND confidence_score >= 0.3
                    AND (1 - (embedding <=> $1::vector)) >= $2
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                    """,
                    str(embedding),
                    threshold,
                    limit,
                )
                return [dict(r) for r in rows]
        except Exception as e:
            logger.warning("search_knowledge_by_vector failed (pgvector?): %s", e)
            return []

    async def search_knowledge(
        self, 
        query: str, 
        limit: int = 10,
        domain_id: Optional[str] = None
    ) -> List[dict]:
        """Поиск по знаниям"""
        if self._pool is None:
            await self.connect()
        
        async with self._pool.acquire() as conn:
            if domain_id:
                rows = await conn.fetch("""
                    SELECT 
                        id,
                        content,
                        metadata,
                        confidence_score,
                        domain_id,
                        created_at
                    FROM knowledge_nodes
                    WHERE content ILIKE $1
                    AND domain_id = $2
                    ORDER BY confidence_score DESC
                    LIMIT $3
                """, f"%{query}%", domain_id, limit)
            else:
                rows = await conn.fetch("""
                    SELECT 
                        id,
                        content,
                        metadata,
                        confidence_score,
                        domain_id,
                        created_at
                    FROM knowledge_nodes
                    WHERE content ILIKE $1
                    ORDER BY confidence_score DESC
                    LIMIT $2
                """, f"%{query}%", limit)
            return [dict(row) for row in rows]
    
    async def get_stats(self) -> dict:
        """Статистика Knowledge OS"""
        if self._pool is None:
            await self.connect()
        
        async with self._pool.acquire() as conn:
            experts_count = await conn.fetchval("SELECT COUNT(*) FROM experts")
            knowledge_count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_nodes")
            domains_count = await conn.fetchval("SELECT COUNT(*) FROM domains")
            
            return {
                "experts": experts_count or 0,
                "knowledge_nodes": knowledge_count or 0,
                "domains": domains_count or 0,
            }


# Singleton (fallback когда пул не в app.state)
knowledge_os_client = KnowledgeOSClient()


async def get_knowledge_os_client(request: Request) -> KnowledgeOSClient:
    """Dependency для FastAPI. Использует пул из app.state (создан в lifespan)."""
    pool = getattr(request.app.state, "knowledge_os_pool", None)
    if pool is not None:
        return KnowledgeOSClient(pool=pool)
    return knowledge_os_client
