"""
Session Context Manager
Управление контекстом сессий пользователей для улучшения качества диалогов
Singularity 8.0: Intelligent Improvements
"""

import asyncio
import logging
import asyncpg
import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

class SessionContextManager:
    """
    Управление контекстом сессий пользователей.
    Сохраняет контекст предыдущих запросов для улучшения качества диалогов.
    """
    
    def __init__(self, db_url: str = DB_URL, max_context_queries: int = 10, session_ttl_hours: int = 24):
        """
        Args:
            db_url: URL базы данных
            max_context_queries: Максимальное количество запросов в контексте
            session_ttl_hours: TTL сессии в часах (24 часа по умолчанию)
        """
        self.db_url = db_url
        self.max_context_queries = max_context_queries
        self.session_ttl_hours = session_ttl_hours
    
    def _generate_session_id(self, user_id: str, expert_name: str) -> str:
        """Генерирует ID сессии на основе user_id и expert_name"""
        import hashlib
        session_key = f"{user_id}_{expert_name}"
        return hashlib.md5(session_key.encode()).hexdigest()
    
    async def get_session_context(
        self,
        user_id: str,
        expert_name: str,
        current_query: str
    ) -> str:
        """
        Получает релевантный контекст из предыдущих запросов в сессии.
        
        Args:
            user_id: ID пользователя
            expert_name: Имя эксперта
            current_query: Текущий запрос
        
        Returns:
            Контекст в виде строки для добавления к промпту
        """
        session_id = self._generate_session_id(user_id, expert_name)
        
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблицы
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'session_context'
                    )
                """)
                
                if not table_exists:
                    return ""
                
                # Получаем последние запросы из сессии (не старше TTL)
                rows = await conn.fetch("""
                    SELECT query_text, response_text, created_at
                    FROM session_context
                    WHERE session_id = $1
                    AND created_at > NOW() - INTERVAL '1 hour' * $2
                    ORDER BY created_at DESC
                    LIMIT $3
                """, session_id, self.session_ttl_hours, self.max_context_queries)
                
                if not rows:
                    return ""
                
                # Формируем контекст (обратный порядок для хронологии)
                context_parts = []
                for row in reversed(rows):  # От старых к новым
                    context_parts.append(f"Q: {row['query_text']}\nA: {row['response_text'][:200]}...")
                
                context = "\n\n".join(context_parts)
                
                # Ограничиваем размер контекста (максимум 500 токенов ≈ 2000 символов)
                if len(context) > 2000:
                    context = context[-2000:]  # Берем последние 2000 символов
                
                logger.debug(f"📝 [SESSION CONTEXT] Получен контекст из {len(rows)} запросов")
                return f"\n\n[КОНТЕКСТ ПРЕДЫДУЩИХ ЗАПРОСОВ В ЭТОЙ СЕССИИ]:\n{context}\n\n"
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"⚠️ [SESSION CONTEXT] Ошибка получения контекста: {e}")
            return ""

    async def get_session_memory_summary(
        self,
        user_id: str,
        expert_name: str,
        max_items: int = 5,
        max_chars: int = 500,
    ) -> str:
        """
        Краткая память по сессии для блока «По этой сессии уже делали» (план «как я»).
        Возвращает последние max_items запросов в формате «запрос → ответ» (обрезано).
        """
        session_id = self._generate_session_id(user_id, expert_name)
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'session_context'
                    )
                """)
                if not table_exists:
                    return ""
                rows = await conn.fetch("""
                    SELECT query_text, response_text
                    FROM session_context
                    WHERE session_id = $1
                    AND created_at > NOW() - INTERVAL '1 hour' * $2
                    ORDER BY created_at DESC
                    LIMIT $3
                """, session_id, self.session_ttl_hours, max_items)
                if not rows:
                    return ""
                parts = []
                for r in reversed(rows):
                    q = (r["query_text"] or "")[:80].replace("\n", " ")
                    a = (r["response_text"] or "")[:80].replace("\n", " ")
                    parts.append(f"• {q} → {a}")
                out = "\n".join(parts)
                return out[:max_chars] if len(out) > max_chars else out
            finally:
                await conn.close()
        except Exception as e:
            logger.debug("get_session_memory_summary: %s", e)
        return ""

    async def save_to_context(
        self,
        user_id: str,
        expert_name: str,
        query: str,
        response: str
    ):
        """
        Сохраняет запрос и ответ в контекст сессии.
        
        Args:
            user_id: ID пользователя
            expert_name: Имя эксперта
            query: Запрос пользователя
            response: Ответ системы
        """
        session_id = self._generate_session_id(user_id, expert_name)
        
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблицы
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'session_context'
                    )
                """)
                
                if not table_exists:
                    return
                
                # Сохраняем запрос и ответ
                await conn.execute("""
                    INSERT INTO session_context (session_id, user_id, expert_name, query_text, response_text, created_at)
                    VALUES ($1, $2, $3, $4, $5, NOW())
                """, session_id, user_id, expert_name, query[:500], response[:2000])  # Ограничиваем длину
                
                # Удаляем старые записи (старше TTL)
                await conn.execute("""
                    DELETE FROM session_context
                    WHERE session_id = $1
                    AND created_at < NOW() - INTERVAL '1 hour' * $2
                """, session_id, self.session_ttl_hours)
                
                # Ограничиваем количество запросов в сессии
                await conn.execute("""
                    DELETE FROM session_context
                    WHERE session_id = $1
                    AND id NOT IN (
                        SELECT id FROM session_context
                        WHERE session_id = $1
                        ORDER BY created_at DESC
                        LIMIT $2
                    )
                """, session_id, self.max_context_queries)
                
                logger.debug(f"💾 [SESSION CONTEXT] Сохранен запрос в контекст сессии {session_id}")
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"⚠️ [SESSION CONTEXT] Ошибка сохранения контекста: {e}")
    
    async def clear_session(self, user_id: str, expert_name: str):
        """
        Очищает контекст сессии.
        
        Args:
            user_id: ID пользователя
            expert_name: Имя эксперта
        """
        session_id = self._generate_session_id(user_id, expert_name)
        
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                await conn.execute("""
                    DELETE FROM session_context
                    WHERE session_id = $1
                """, session_id)
                logger.debug(f"🗑️ [SESSION CONTEXT] Очищен контекст сессии {session_id}")
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"⚠️ [SESSION CONTEXT] Ошибка очистки контекста: {e}")
    
    async def cleanup_old_sessions(self):
        """Очищает устаревшие сессии (старше TTL)"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                deleted = await conn.execute("""
                    DELETE FROM session_context
                    WHERE created_at < NOW() - INTERVAL '1 hour' * $1
                """, self.session_ttl_hours)
                
                deleted_count = int(deleted.split()[-1]) if deleted else 0
                if deleted_count > 0:
                    logger.info(f"🧹 [SESSION CONTEXT] Очищено {deleted_count} устаревших записей")
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"⚠️ [SESSION CONTEXT] Ошибка очистки старых сессий: {e}")

# Singleton instance
_context_manager_instance: Optional[SessionContextManager] = None

def get_session_context_manager(
    max_context_queries: int = 10,
    session_ttl_hours: int = 24
) -> SessionContextManager:
    """Получить singleton экземпляр менеджера контекста"""
    global _context_manager_instance
    if _context_manager_instance is None:
        _context_manager_instance = SessionContextManager(
            max_context_queries=max_context_queries,
            session_ttl_hours=session_ttl_hours
        )
    return _context_manager_instance

