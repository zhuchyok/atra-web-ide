"""
ML Router Data Collector
Собирает данные о решениях роутера для обучения ML-модели
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

class MLRouterDataCollector:
    """
    Собирает данные о решениях роутера для обучения ML-модели.
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
    
    async def collect_routing_decision(
        self,
        task_type: str,
        prompt_length: int,
        category: Optional[str],
        selected_route: str,
        performance_score: Optional[float] = None,
        tokens_saved: int = 0,
        latency_ms: Optional[float] = None,
        quality_score: Optional[float] = None,
        success: bool = True,
        features: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Сохраняет решение роутера в БД для обучения ML-модели.
        
        Args:
            task_type: Тип задачи (coding, reasoning, general)
            prompt_length: Длина промпта в символах
            category: Категория задачи
            selected_route: Выбранный маршрут (local_mac, local_server, cloud)
            performance_score: Оценка производительности (0.0-1.0)
            tokens_saved: Количество сэкономленных токенов
            latency_ms: Задержка в миллисекундах
            quality_score: Оценка качества ответа (0.0-1.0)
            success: Успешность выполнения
            features: Дополнительные features для ML
        
        Returns:
            True если успешно сохранено
        """
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO ml_routing_training_data 
                    (task_type, prompt_length, category, selected_route, 
                     performance_score, tokens_saved, latency_ms, quality_score, 
                     success, features, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
                """, 
                task_type, prompt_length, category, selected_route,
                performance_score, tokens_saved, latency_ms, quality_score,
                success, json.dumps(features) if features else None)
                
                logger.debug(f"✅ [ML DATA] Saved routing decision: {selected_route} for {task_type}")
                return True
        except Exception as e:
            logger.error(f"❌ [ML DATA] Error saving routing decision: {e}")
            return False
    
    async def collect_prediction(
        self,
        task_type: str,
        prompt_length: int,
        category: Optional[str],
        predicted_route: str,
        confidence: Optional[float] = None,
        actual_route: Optional[str] = None,
        was_correct: Optional[bool] = None,
        features: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Сохраняет предсказание ML-модели для анализа.
        
        Args:
            task_type: Тип задачи
            prompt_length: Длина промпта
            category: Категория задачи
            predicted_route: Предсказанный маршрут
            confidence: Уверенность предсказания (0.0-1.0)
            actual_route: Фактический выбранный маршрут
            was_correct: Было ли предсказание правильным
            features: Дополнительные features
        
        Returns:
            True если успешно сохранено
        """
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO ml_router_predictions
                    (task_type, prompt_length, category, predicted_route,
                     confidence, actual_route, was_correct, features, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                """,
                task_type, prompt_length, category, predicted_route,
                confidence, actual_route, was_correct, 
                json.dumps(features) if features else None)
                
                logger.debug(f"✅ [ML DATA] Saved prediction: {predicted_route} (confidence: {confidence})")
                return True
        except Exception as e:
            logger.error(f"❌ [ML DATA] Error saving prediction: {e}")
            return False
    
    async def get_training_data_count(self, days: int = 30) -> int:
        """Получает количество примеров для обучения за последние N дней"""
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval(f"""
                    SELECT COUNT(*) 
                    FROM ml_routing_training_data
                    WHERE created_at > NOW() - INTERVAL '{days} days'
                """)
                return count or 0
        except Exception as e:
            logger.error(f"❌ [ML DATA] Error getting training data count: {e}")
            return 0
    
    async def get_training_data(
        self, 
        limit: int = 1000,
        days: int = 30
    ) -> list:
        """Получает данные для обучения"""
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(f"""
                    SELECT 
                        task_type, prompt_length, category, selected_route,
                        performance_score, tokens_saved, latency_ms, quality_score,
                        success, features
                    FROM ml_routing_training_data
                    WHERE created_at > NOW() - INTERVAL '{days} days'
                    ORDER BY created_at DESC
                    LIMIT $1
                """, limit)
                
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ [ML DATA] Error getting training data: {e}")
            return []
    
    async def close(self):
        """Закрывает connection pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None

# Singleton instance
_collector_instance = None

async def get_collector() -> MLRouterDataCollector:
    """Получает singleton instance коллектора"""
    global _collector_instance
    if _collector_instance is None:
        _collector_instance = MLRouterDataCollector()
    return _collector_instance

