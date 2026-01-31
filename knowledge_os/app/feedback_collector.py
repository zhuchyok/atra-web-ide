"""
Feedback Collector
Собирает feedback от пользователей и системы для адаптивного обучения
"""

import asyncio
import logging
import asyncpg
import os
import json
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

class FeedbackCollector:
    """
    Собирает feedback для адаптивного обучения.
    """
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self._pool = None
    
    async def _get_pool(self):
        """Получает connection pool"""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.db_url,
                min_size=1,
                max_size=5
            )
        return self._pool
    
    async def collect_implicit_feedback(
        self,
        query: str,
        response: str,
        routing_source: str,
        rerouted_to_cloud: bool = False,
        reroute_reason: Optional[str] = None,
        quality_score: Optional[float] = None
    ) -> bool:
        """
        Собирает неявный feedback (reroute в облако = негативный).
        
        Args:
            query: Исходный запрос
            response: Ответ системы
            routing_source: Источник ответа (local_mac, local_server, cloud)
            rerouted_to_cloud: Был ли ответ перенаправлен в облако
            reroute_reason: Причина reroute (low_quality, safety_check_failed, etc.)
            quality_score: Оценка качества ответа
        
        Returns:
            True если успешно сохранено
        """
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                # Проверяем существование таблицы
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'feedback_data'
                    )
                """)
                
                if not table_exists:
                    # Создаем таблицу
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS feedback_data (
                            id SERIAL PRIMARY KEY,
                            query TEXT NOT NULL,
                            response TEXT,
                            routing_source VARCHAR(50),
                            rerouted_to_cloud BOOLEAN DEFAULT FALSE,
                            reroute_reason VARCHAR(100),
                            quality_score FLOAT,
                            feedback_type VARCHAR(50) DEFAULT 'implicit',
                            is_positive BOOLEAN,
                            metadata JSONB,
                            created_at TIMESTAMP DEFAULT NOW()
                        );
                        
                        CREATE INDEX IF NOT EXISTS idx_feedback_routing_source 
                        ON feedback_data(routing_source);
                        
                        CREATE INDEX IF NOT EXISTS idx_feedback_rerouted 
                        ON feedback_data(rerouted_to_cloud);
                        
                        CREATE INDEX IF NOT EXISTS idx_feedback_created_at 
                        ON feedback_data(created_at);
                    """)
                
                # Определяем, позитивный ли feedback
                # Reroute в облако = негативный
                is_positive = not rerouted_to_cloud
                if quality_score is not None:
                    is_positive = quality_score >= 0.7
                
                await conn.execute("""
                    INSERT INTO feedback_data
                    (query, response, routing_source, rerouted_to_cloud, 
                     reroute_reason, quality_score, feedback_type, is_positive, 
                     metadata, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                """,
                query[:1000],  # Ограничиваем длину
                response[:2000] if response else None,
                routing_source,
                rerouted_to_cloud,
                reroute_reason,
                quality_score,
                'implicit',
                is_positive,
                json.dumps({
                    'query_length': len(query),
                    'response_length': len(response) if response else 0
                }))
                
                logger.debug(f"✅ [FEEDBACK] Collected implicit feedback: rerouted={rerouted_to_cloud}, positive={is_positive}")
                return True
        except Exception as e:
            logger.error(f"❌ [FEEDBACK] Error collecting feedback: {e}")
            return False
    
    async def collect_explicit_feedback(
        self,
        user_id: str,
        expert_name: str,
        query: str,
        response: str,
        feedback_type: str,  # 'positive' или 'negative'
        rating: Optional[int] = None,
        comment: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Собирает явный feedback от пользователя (👍/👎).
        
        Args:
            user_id: ID пользователя
            expert_name: Имя эксперта
            query: Исходный запрос
            response: Ответ системы
            feedback_type: Тип feedback ('positive' для 👍, 'negative' для 👎)
            rating: Опциональная оценка (1-5)
            comment: Опциональный комментарий
            metadata: Дополнительные данные (routing_source, performance_score, etc.)
        
        Returns:
            True если успешно сохранено
        """
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                # Проверяем наличие таблицы user_feedback
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'user_feedback'
                    )
                """)
                
                if not table_exists:
                    logger.warning("⚠️ [FEEDBACK] Таблица user_feedback не найдена, используем feedback_data")
                    # Fallback на старую таблицу
                    is_positive = feedback_type == 'positive'
                    await conn.execute("""
                        INSERT INTO feedback_data
                        (query, response, feedback_type, is_positive, metadata, created_at)
                        VALUES ($1, $2, $3, $4, $5, NOW())
                    """,
                    query[:1000],
                    response[:2000] if response else None,
                    'explicit',
                    is_positive,
                    json.dumps({
                        'rating': rating,
                        'comment': comment,
                        'user_id': user_id,
                        'expert_name': expert_name,
                        **(metadata or {})
                    }))
                else:
                    # Используем новую таблицу user_feedback
                    await conn.execute("""
                        INSERT INTO user_feedback
                        (user_id, expert_name, query_text, response_text, feedback_type, rating, comment, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    user_id,
                    expert_name,
                    query[:1000],
                    response[:2000] if response else None,
                    feedback_type,
                    rating,
                    comment,
                    json.dumps(metadata) if metadata else None)
                
                logger.info(f"✅ [FEEDBACK] Collected explicit feedback: {feedback_type} (user: {user_id}, expert: {expert_name})")
                return True
        except Exception as e:
            logger.error(f"❌ [FEEDBACK] Error collecting explicit feedback: {e}")
            return False
    
    async def get_feedback_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Получает статистику feedback"""
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                # Проверяем существование таблицы
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'feedback_data'
                    )
                """)
                
                if not table_exists:
                    return {
                        'total': 0,
                        'positive': 0,
                        'negative': 0,
                        'reroute_rate': 0.0
                    }
                
                stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE is_positive = TRUE) as positive,
                        COUNT(*) FILTER (WHERE is_positive = FALSE) as negative,
                        COUNT(*) FILTER (WHERE rerouted_to_cloud = TRUE) as rerouted
                    FROM feedback_data
                    WHERE created_at > NOW() - INTERVAL '%s days'
                """, days)
                
                total = stats['total'] or 0
                positive = stats['positive'] or 0
                negative = stats['negative'] or 0
                rerouted = stats['rerouted'] or 0
                
                return {
                    'total': total,
                    'positive': positive,
                    'negative': negative,
                    'reroute_rate': (rerouted / total) if total > 0 else 0.0,
                    'positive_rate': (positive / total) if total > 0 else 0.0
                }
        except Exception as e:
            logger.error(f"❌ [FEEDBACK] Error getting statistics: {e}")
            return {
                'total': 0,
                'positive': 0,
                'negative': 0,
                'reroute_rate': 0.0
            }
    
    async def close(self):
        """Закрывает connection pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None

# Singleton instance
_feedback_collector_instance = None

async def get_feedback_collector() -> FeedbackCollector:
    """Получает singleton instance feedback collector"""
    global _feedback_collector_instance
    if _feedback_collector_instance is None:
        _feedback_collector_instance = FeedbackCollector()
    return _feedback_collector_instance

