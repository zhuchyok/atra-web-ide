"""
ML Router A/B Testing
Система A/B тестирования для сравнения ML-роутинга и эвристического роутинга
"""

import asyncio
import logging
import random
import asyncpg
import os
from typing import Dict, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

class MLRouterABTest:
    """
    Система A/B тестирования для сравнения ML-роутинга и эвристического роутинга.
    """
    
    def __init__(self, ml_ratio: float = 0.5, db_url: str = DB_URL):
        """
        Args:
            ml_ratio: Доля трафика для ML-роутинга (0.0-1.0)
            db_url: URL базы данных
        """
        self.ml_ratio = ml_ratio
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
    
    def should_use_ml(self) -> bool:
        """
        Определяет, использовать ли ML-роутинг для текущего запроса.
        Использует случайное распределение на основе ml_ratio.
        """
        return random.random() < self.ml_ratio
    
    async def log_ab_test_result(
        self,
        request_id: str,
        used_ml: bool,
        selected_route: str,
        performance_score: Optional[float] = None,
        tokens_saved: int = 0,
        latency_ms: Optional[float] = None,
        quality_score: Optional[float] = None,
        success: bool = True
    ):
        """
        Логирует результат A/B теста.
        
        Args:
            request_id: Уникальный ID запроса
            used_ml: Использовался ли ML-роутинг
            selected_route: Выбранный маршрут
            performance_score: Оценка производительности
            tokens_saved: Сэкономленные токены
            latency_ms: Задержка в миллисекундах
            quality_score: Оценка качества
            success: Успешность выполнения
        """
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                # Проверяем, существует ли таблица
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'ml_router_ab_test'
                    )
                """)
                
                if not table_exists:
                    # Создаем таблицу если не существует
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS ml_router_ab_test (
                            id SERIAL PRIMARY KEY,
                            request_id VARCHAR(255) UNIQUE NOT NULL,
                            used_ml BOOLEAN NOT NULL,
                            selected_route VARCHAR(50) NOT NULL,
                            performance_score FLOAT,
                            tokens_saved INTEGER DEFAULT 0,
                            latency_ms FLOAT,
                            quality_score FLOAT,
                            success BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT NOW()
                        );
                        
                        CREATE INDEX IF NOT EXISTS idx_ab_test_used_ml 
                        ON ml_router_ab_test(used_ml);
                        
                        CREATE INDEX IF NOT EXISTS idx_ab_test_created_at 
                        ON ml_router_ab_test(created_at);
                    """)
                
                await conn.execute("""
                    INSERT INTO ml_router_ab_test
                    (request_id, used_ml, selected_route, performance_score, 
                     tokens_saved, latency_ms, quality_score, success, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                    ON CONFLICT (request_id) DO UPDATE
                    SET selected_route = EXCLUDED.selected_route,
                        performance_score = EXCLUDED.performance_score,
                        tokens_saved = EXCLUDED.tokens_saved,
                        latency_ms = EXCLUDED.latency_ms,
                        quality_score = EXCLUDED.quality_score,
                        success = EXCLUDED.success
                """,
                request_id, used_ml, selected_route, performance_score,
                tokens_saved, latency_ms, quality_score, success)
                
                logger.debug(f"✅ [AB TEST] Logged result: ML={used_ml}, route={selected_route}")
        except Exception as e:
            logger.error(f"❌ [AB TEST] Error logging result: {e}")
    
    async def get_ab_test_statistics(self, days: int = 7) -> Dict[str, Any]:
        """
        Получает статистику A/B тестирования.
        
        Returns:
            Словарь со статистикой по ML и эвристическому роутингу
        """
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                # Проверяем существование таблицы
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'ml_router_ab_test'
                    )
                """)
                
                if not table_exists:
                    return {
                        'ml': {'count': 0, 'avg_performance': 0, 'avg_tokens_saved': 0, 'success_rate': 0},
                        'heuristic': {'count': 0, 'avg_performance': 0, 'avg_tokens_saved': 0, 'success_rate': 0}
                    }
                
                # Статистика для ML-роутинга
                ml_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as count,
                        AVG(performance_score) as avg_performance,
                        AVG(tokens_saved) as avg_tokens_saved,
                        AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as success_rate
                    FROM ml_router_ab_test
                    WHERE used_ml = TRUE
                    AND created_at > NOW() - INTERVAL '%s days'
                """, days)
                
                # Статистика для эвристического роутинга
                heuristic_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as count,
                        AVG(performance_score) as avg_performance,
                        AVG(tokens_saved) as avg_tokens_saved,
                        AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as success_rate
                    FROM ml_router_ab_test
                    WHERE used_ml = FALSE
                    AND created_at > NOW() - INTERVAL '%s days'
                """, days)
                
                return {
                    'ml': {
                        'count': ml_stats['count'] or 0,
                        'avg_performance': float(ml_stats['avg_performance'] or 0),
                        'avg_tokens_saved': float(ml_stats['avg_tokens_saved'] or 0),
                        'success_rate': float(ml_stats['success_rate'] or 0)
                    },
                    'heuristic': {
                        'count': heuristic_stats['count'] or 0,
                        'avg_performance': float(heuristic_stats['avg_performance'] or 0),
                        'avg_tokens_saved': float(heuristic_stats['avg_tokens_saved'] or 0),
                        'success_rate': float(heuristic_stats['success_rate'] or 0)
                    }
                }
        except Exception as e:
            logger.error(f"❌ [AB TEST] Error getting statistics: {e}")
            return {
                'ml': {'count': 0, 'avg_performance': 0, 'avg_tokens_saved': 0, 'success_rate': 0},
                'heuristic': {'count': 0, 'avg_performance': 0, 'avg_tokens_saved': 0, 'success_rate': 0}
            }
    
    async def should_switch_to_ml(self, min_samples: int = 100, improvement_threshold: float = 0.1) -> bool:
        """
        Определяет, следует ли переключиться полностью на ML-роутинг.
        
        Args:
            min_samples: Минимальное количество образцов для каждого варианта
            improvement_threshold: Минимальное улучшение для переключения (10%)
        
        Returns:
            True если следует переключиться на ML
        """
        stats = await self.get_ab_test_statistics()
        
        ml_count = stats['ml']['count']
        heuristic_count = stats['heuristic']['count']
        
        # Проверяем достаточность данных
        if ml_count < min_samples or heuristic_count < min_samples:
            return False
        
        # Сравниваем метрики
        ml_tokens = stats['ml']['avg_tokens_saved']
        heuristic_tokens = stats['heuristic']['avg_tokens_saved']
        
        ml_performance = stats['ml']['avg_performance']
        heuristic_performance = stats['heuristic']['avg_performance']
        
        # ML должен быть лучше по токенам и не хуже по качеству
        tokens_improvement = (ml_tokens - heuristic_tokens) / max(heuristic_tokens, 1)
        performance_diff = ml_performance - heuristic_performance
        
        if tokens_improvement >= improvement_threshold and performance_diff >= -0.05:
            logger.info(f"✅ [AB TEST] ML routing shows improvement: {tokens_improvement:.2%} more tokens saved")
            return True
        
        return False
    
    async def close(self):
        """Закрывает connection pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None

# Singleton instance
_ab_test_instance = None

async def get_ab_test(ml_ratio: float = 0.5) -> MLRouterABTest:
    """Получает singleton instance A/B теста"""
    global _ab_test_instance
    if _ab_test_instance is None:
        _ab_test_instance = MLRouterABTest(ml_ratio=ml_ratio)
    return _ab_test_instance

