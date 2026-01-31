"""
Usage Analytics
Детальная аналитика использования системы
Singularity 8.0: Monitoring and Analytics
"""

import asyncio
import logging
import asyncpg
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

class UsageAnalytics:
    """
    Аналитика использования системы.
    Собирает статистику по пользователям, экспертам и моделям.
    """
    
    def __init__(self, db_url: str = DB_URL):
        """
        Args:
            db_url: URL базы данных
        """
        self.db_url = db_url
    
    async def collect_request_analytics(
        self,
        user_id: str,
        expert_name: str,
        query: str,
        response: str,
        routing_source: Optional[str] = None,
        latency_ms: Optional[float] = None,
        tokens_used: Optional[int] = None
    ):
        """
        Собирает аналитику по запросу.
        
        Args:
            user_id: ID пользователя
            expert_name: Имя эксперта
            query: Запрос
            response: Ответ
            routing_source: Источник ответа
            latency_ms: Latency в миллисекундах
            tokens_used: Количество использованных токенов
        """
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблиц
                user_analytics_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'user_analytics'
                    )
                """)
                
                if not user_analytics_exists:
                    return
                
                # Сохраняем в user_analytics
                await conn.execute("""
                    INSERT INTO user_analytics 
                    (user_id, query_text, query_length, response_length, created_at)
                    VALUES ($1, $2, $3, $4, NOW())
                """, user_id, query[:500], len(query), len(response))
                
                # Сохраняем в expert_analytics
                expert_analytics_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'expert_analytics'
                    )
                """)
                
                if expert_analytics_exists:
                    await conn.execute("""
                        INSERT INTO expert_analytics 
                        (expert_name, request_count, created_at)
                        VALUES ($1, 1, NOW())
                        ON CONFLICT (expert_name, DATE(created_at)) 
                        DO UPDATE SET request_count = expert_analytics.request_count + 1
                    """, expert_name)
                
                # Сохраняем в model_analytics
                if routing_source:
                    model_analytics_exists = await conn.fetchval("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_name = 'model_analytics'
                        )
                    """)
                    
                    if model_analytics_exists:
                        await conn.execute("""
                            INSERT INTO model_analytics 
                            (model_name, request_count, avg_latency_ms, total_tokens, created_at)
                            VALUES ($1, 1, $2, $3, NOW())
                            ON CONFLICT (model_name, DATE(created_at))
                            DO UPDATE SET 
                                request_count = model_analytics.request_count + 1,
                                avg_latency_ms = (model_analytics.avg_latency_ms * model_analytics.request_count + $2) / (model_analytics.request_count + 1),
                                total_tokens = model_analytics.total_tokens + $3
                        """, routing_source, latency_ms or 0, tokens_used or 0)
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"⚠️ [USAGE ANALYTICS] Ошибка сбора аналитики: {e}")
    
    async def get_user_analytics(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        """
        Получает аналитику по пользователю.
        
        Args:
            user_id: ID пользователя
            days: Количество дней
        
        Returns:
            Словарь с аналитикой
        """
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблицы
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'user_analytics'
                    )
                """)
                
                if not table_exists:
                    return {}
                
                stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_requests,
                        AVG(query_length) as avg_query_length,
                        AVG(response_length) as avg_response_length,
                        COUNT(DISTINCT DATE(created_at)) as active_days
                    FROM user_analytics
                    WHERE user_id = $1
                    AND created_at > NOW() - INTERVAL '1 day' * $2
                """, user_id, days)
                
                # Топ запросы
                top_queries = await conn.fetch("""
                    SELECT query_text, COUNT(*) as count
                    FROM user_analytics
                    WHERE user_id = $1
                    AND created_at > NOW() - INTERVAL '1 day' * $2
                    GROUP BY query_text
                    ORDER BY count DESC
                    LIMIT 10
                """, user_id, days)
                
                return {
                    "total_requests": stats['total_requests'] or 0,
                    "avg_query_length": float(stats['avg_query_length'] or 0),
                    "avg_response_length": float(stats['avg_response_length'] or 0),
                    "active_days": stats['active_days'] or 0,
                    "top_queries": [{"query": row['query_text'], "count": row['count']} for row in top_queries]
                }
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ [USAGE ANALYTICS] Ошибка получения аналитики пользователя: {e}")
            return {}
    
    async def get_expert_analytics(self, days: int = 7) -> Dict[str, Any]:
        """
        Получает аналитику по экспертам.
        
        Args:
            days: Количество дней
        
        Returns:
            Словарь с аналитикой
        """
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблицы
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'expert_analytics'
                    )
                """)
                
                if not table_exists:
                    return {}
                
                stats = await conn.fetch("""
                    SELECT 
                        expert_name,
                        SUM(request_count) as total_requests
                    FROM expert_analytics
                    WHERE created_at > NOW() - INTERVAL '1 day' * $1
                    GROUP BY expert_name
                    ORDER BY total_requests DESC
                """, days)
                
                return {
                    "experts": [
                        {"name": row['expert_name'], "requests": row['total_requests']}
                        for row in stats
                    ]
                }
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ [USAGE ANALYTICS] Ошибка получения аналитики экспертов: {e}")
            return {}
    
    async def get_model_analytics(self, days: int = 7) -> Dict[str, Any]:
        """
        Получает аналитику по моделям.
        
        Args:
            days: Количество дней
        
        Returns:
            Словарь с аналитикой
        """
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблицы
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'model_analytics'
                    )
                """)
                
                if not table_exists:
                    return {}
                
                stats = await conn.fetch("""
                    SELECT 
                        model_name,
                        SUM(request_count) as total_requests,
                        AVG(avg_latency_ms) as avg_latency,
                        SUM(total_tokens) as total_tokens
                    FROM model_analytics
                    WHERE created_at > NOW() - INTERVAL '1 day' * $1
                    GROUP BY model_name
                    ORDER BY total_requests DESC
                """, days)
                
                return {
                    "models": [
                        {
                            "name": row['model_name'],
                            "requests": row['total_requests'],
                            "avg_latency_ms": float(row['avg_latency'] or 0),
                            "total_tokens": row['total_tokens'] or 0
                        }
                        for row in stats
                    ]
                }
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ [USAGE ANALYTICS] Ошибка получения аналитики моделей: {e}")
            return {}

# Singleton instance
_usage_analytics_instance: Optional[UsageAnalytics] = None

def get_usage_analytics(db_url: str = DB_URL) -> UsageAnalytics:
    """Получить singleton экземпляр аналитики"""
    global _usage_analytics_instance
    if _usage_analytics_instance is None:
        _usage_analytics_instance = UsageAnalytics(db_url=db_url)
    return _usage_analytics_instance

