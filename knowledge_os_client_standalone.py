"""
Knowledge OS Client (Standalone)
Интеграция с базой знаний Singularity.
Переименован из knowledge_os.py чтобы не затенять пакет knowledge_os/ при импортах тестов.
Backend использует app.services.knowledge_os.
"""
import asyncpg
import os
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


class KnowledgeOSClient:
    """Клиент для Knowledge OS Database"""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or DATABASE_URL
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Создать пул соединений"""
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(
                    self.database_url,
                    min_size=2,
                    max_size=10
                )
                logger.info("✅ Knowledge OS DB connected")
            except Exception as e:
                logger.error("❌ Knowledge OS DB connection failed: %s", e)
                raise

    async def disconnect(self):
        """Закрыть пул соединений"""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def get_experts(self) -> List[dict]:
        """Получить список всех экспертов"""
        if self._pool is None:
            await self.connect()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, role, system_prompt, created_at FROM experts ORDER BY name"
            )
            return [dict(row) for row in rows]

    async def get_expert(self, expert_id: str) -> Optional[dict]:
        """Получить эксперта по ID"""
        if self._pool is None:
            await self.connect()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id, name, role, system_prompt, created_at FROM experts WHERE id = $1", expert_id)
            return dict(row) if row else None

    async def get_expert_by_name(self, name: str) -> Optional[dict]:
        """Получить эксперта по имени"""
        if self._pool is None:
            await self.connect()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id, name, role, system_prompt, created_at FROM experts WHERE name ILIKE $1", f"%{name}%")
            return dict(row) if row else None

    async def get_domains(self) -> List[dict]:
        """Получить список доменов"""
        if self._pool is None:
            await self.connect()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, name, description, created_at FROM domains ORDER BY name")
            return [dict(row) for row in rows]

    async def search_knowledge(self, query: str, limit: int = 10, domain_id: Optional[str] = None) -> List[dict]:
        """Поиск по знаниям"""
        if self._pool is None:
            await self.connect()
        async with self._pool.acquire() as conn:
            if domain_id:
                rows = await conn.fetch("""
                    SELECT id, content, metadata, confidence_score, domain_id, created_at
                    FROM knowledge_nodes WHERE content ILIKE $1 AND domain_id = $2
                    ORDER BY confidence_score DESC LIMIT $3
                """, f"%{query}%", domain_id, limit)
            else:
                rows = await conn.fetch("""
                    SELECT id, content, metadata, confidence_score, domain_id, created_at
                    FROM knowledge_nodes WHERE content ILIKE $1 ORDER BY confidence_score DESC LIMIT $2
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


knowledge_os_client = KnowledgeOSClient()


async def get_knowledge_os_client() -> KnowledgeOSClient:
    """Dependency для FastAPI"""
    return knowledge_os_client
