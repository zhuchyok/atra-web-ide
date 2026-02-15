"""
Долгосрочная память по пользователю/проекту (План «Логика мысли» Фаза 2).
Хранит суммаризованные обмены (goal + outcome) для блока «Ранее по этому проекту/пользователю».
Ключ: (user_key, project_context). user_key = session_id от клиента.
"""

import logging
import os
from typing import Optional, List

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

# Лимиты по умолчанию (env переопределяют)
LONG_TERM_MEMORY_TTL_DAYS = int(os.getenv("LONG_TERM_MEMORY_TTL_DAYS", "7"))
LONG_TERM_MEMORY_MAX_THREADS = int(os.getenv("LONG_TERM_MEMORY_MAX_THREADS", "20"))
LONG_TERM_MEMORY_GOAL_MAX = 500
LONG_TERM_MEMORY_OUTCOME_MAX = 500


class LongTermMemoryManager:
    """Сохранение и выборка «нитей» долгосрочной памяти по (user_key, project_context)."""

    def __init__(
        self,
        db_url: str = DB_URL,
        ttl_days: int = LONG_TERM_MEMORY_TTL_DAYS,
        max_threads_per_key: int = LONG_TERM_MEMORY_MAX_THREADS,
    ):
        self.db_url = db_url
        self.ttl_days = max(1, ttl_days)
        self.max_threads_per_key = max(1, min(max_threads_per_key, 100))

    async def save_thread(
        self,
        user_key: str,
        project_context: str,
        goal_summary: str,
        outcome_summary: str,
        embedding: Optional[List[float]] = None,
    ) -> None:
        """Сохранить одну «нить» (запрос + итог). Ограничение длины и лимит записей по ключу."""
        if not user_key or not project_context:
            return
        goal_summary = (goal_summary or "")[:LONG_TERM_MEMORY_GOAL_MAX].strip()
        outcome_summary = (outcome_summary or "")[:LONG_TERM_MEMORY_OUTCOME_MAX].strip()
        if not goal_summary and not outcome_summary:
            return
        try:
            import asyncpg
            conn = await asyncpg.connect(self.db_url)
            try:
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'long_term_memory'
                    )
                """)
                if not table_exists:
                    logger.debug("long_term_memory: таблица не найдена, пропуск сохранения")
                    return
                
                if embedding:
                    await conn.execute("""
                        INSERT INTO long_term_memory (user_key, project_context, goal_summary, outcome_summary, embedding)
                        VALUES ($1, $2, $3, $4, $5)
                    """, user_key, project_context or "default", goal_summary, outcome_summary, embedding)
                else:
                    await conn.execute("""
                        INSERT INTO long_term_memory (user_key, project_context, goal_summary, outcome_summary)
                        VALUES ($1, $2, $3, $4)
                    """, user_key, project_context or "default", goal_summary, outcome_summary)
                
                # Удалить старые по TTL
                await conn.execute("""
                    DELETE FROM long_term_memory
                    WHERE (user_key, project_context) = ($1, $2)
                    AND created_at < NOW() - ($3 || ' days')::INTERVAL
                """, user_key, project_context or "default", self.ttl_days)
                # Оставить только последние max_threads_per_key
                await conn.execute("""
                    DELETE FROM long_term_memory
                    WHERE (user_key, project_context) = ($1, $2)
                    AND id NOT IN (
                        SELECT id FROM long_term_memory
                        WHERE user_key = $1 AND project_context = $2
                        ORDER BY created_at DESC
                        LIMIT $3
                    )
                """, user_key, project_context or "default", self.max_threads_per_key)
            finally:
                await conn.close()
        except Exception as e:
            logger.debug("long_term_memory save_thread: %s", e)

    async def get_relevant_threads(
        self,
        query_embedding: List[float],
        project_context: str,
        user_key: Optional[str] = None,
        limit: int = 5,
        min_similarity: float = 0.3,
        max_chars: int = 800,
    ) -> str:
        """
        Поиск семантически похожих «нитей» памяти по вектору.
        Возвращает строку для блока «Ранее по этому проекту/пользователю».
        """
        if not query_embedding or not project_context:
            return ""
        try:
            import asyncpg
            conn = await asyncpg.connect(self.db_url)
            try:
                # Поиск по косинусному расстоянию (<=>)
                # similarity = 1 - distance
                if user_key:
                    rows = await conn.fetch("""
                        SELECT goal_summary, outcome_summary, (1 - (embedding <=> $1)) as similarity
                        FROM long_term_memory
                        WHERE project_context = $2 AND user_key = $3
                        AND embedding IS NOT NULL
                        AND (1 - (embedding <=> $1)) >= $4
                        ORDER BY embedding <=> $1
                        LIMIT $5
                    """, query_embedding, project_context, user_key, min_similarity, limit)
                else:
                    rows = await conn.fetch("""
                        SELECT goal_summary, outcome_summary, (1 - (embedding <=> $1)) as similarity
                        FROM long_term_memory
                        WHERE project_context = $2
                        AND embedding IS NOT NULL
                        AND (1 - (embedding <=> $1)) >= $3
                        ORDER BY embedding <=> $1
                        LIMIT $4
                    """, query_embedding, project_context, min_similarity, limit)
                
                if not rows:
                    return ""
                
                parts: List[str] = []
                for r in rows:
                    g = (r["goal_summary"] or "").replace("\n", " ").strip()
                    o = (r["outcome_summary"] or "").replace("\n", " ").strip()
                    sim = r["similarity"]
                    parts.append(f"• [sim={sim:.2f}] {g} → {o}")
                
                out = "\n".join(parts)
                return out[:max_chars] if len(out) > max_chars else out
            finally:
                await conn.close()
        except Exception as e:
            logger.debug("long_term_memory get_relevant_threads: %s", e)
        return ""

    async def get_recent_threads(
        self,
        user_key: str,
        project_context: str,
        limit: int = 5,
        max_chars: int = 600,
    ) -> str:
        """
        До K последних «нитей» по (user_key, project_context) для подмешивания в контекст.
        Возвращает строку для блока «Ранее по этому проекту/пользователю» или пустую.
        """
        if not user_key and not project_context:
            return ""
        try:
            import asyncpg
            conn = await asyncpg.connect(self.db_url)
            try:
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'long_term_memory'
                    )
                """)
                if not table_exists:
                    return ""
                # Выборка по user_key + project_context (если оба заданы) или по project_context только
                if user_key and project_context:
                    rows = await conn.fetch("""
                        SELECT goal_summary, outcome_summary, created_at
                        FROM long_term_memory
                        WHERE user_key = $1 AND project_context = $2
                        AND created_at > NOW() - ($4 || ' days')::INTERVAL
                        ORDER BY created_at DESC
                        LIMIT $3
                    """, user_key, project_context or "default", limit, self.ttl_days)
                elif project_context:
                    rows = await conn.fetch("""
                        SELECT goal_summary, outcome_summary, created_at
                        FROM long_term_memory
                        WHERE project_context = $1
                        AND created_at > NOW() - ($3 || ' days')::INTERVAL
                        ORDER BY created_at DESC
                        LIMIT $2
                    """, project_context or "default", limit, self.ttl_days)
                else:
                    return ""
                if not rows:
                    return ""
                parts: List[str] = []
                for r in reversed(rows):
                    g = (r["goal_summary"] or "").replace("\n", " ").strip()
                    o = (r["outcome_summary"] or "").replace("\n", " ").strip()
                    parts.append(f"• {g} → {o}")
                out = "\n".join(parts)
                return out[:max_chars] if len(out) > max_chars else out
            finally:
                await conn.close()
        except Exception as e:
            logger.debug("long_term_memory get_recent_threads: %s", e)
        return ""


_manager_instance: Optional[LongTermMemoryManager] = None


def get_long_term_memory_manager() -> LongTermMemoryManager:
    """Singleton менеджера долгосрочной памяти."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = LongTermMemoryManager(
            ttl_days=LONG_TERM_MEMORY_TTL_DAYS,
            max_threads_per_key=LONG_TERM_MEMORY_MAX_THREADS,
        )
    return _manager_instance
