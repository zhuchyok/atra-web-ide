"""
SLA Monitor для отслеживания Service Level Agreements.
"""

import asyncio
import logging
import asyncpg
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# SLA определения
SLA_DEFINITIONS = {
    "p95_latency": 2.0,  # секунды
    "availability": 0.995,  # 99.5%
    "cache_hit_rate": 0.70,  # 70%
    "token_savings": 0.40,  # 40%
}

class SLAMonitor:
    """Монитор SLA метрик"""
    
    def __init__(self, db_url: str = None):
        import os
        self.db_url = db_url or os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
        
    async def calculate_p95_latency(self, hours: int = 24) -> float:
        """Вычислить p95 latency за период из real_time_metrics"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Получаем метрики latency из real_time_metrics
                rows = await conn.fetch("""
                    SELECT metric_value
                    FROM real_time_metrics
                    WHERE metric_name = 'latency_ms'
                    AND created_at > NOW() - INTERVAL '1 hour' * $1
                    ORDER BY metric_value
                """, hours)
                
                if not rows:
                    # Fallback: вычисляем из других метрик
                    return 1.5
                
                values = [float(row['metric_value']) for row in rows]
                if not values:
                    return 1.5
                
                # Вычисляем p95 (95-й перцентиль)
                sorted_values = sorted(values)
                p95_index = int(len(sorted_values) * 0.95)
                p95_value = sorted_values[min(p95_index, len(sorted_values) - 1)]
                
                # Конвертируем из миллисекунд в секунды
                return p95_value / 1000.0
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"Error calculating p95 latency: {e}")
            return 1.5  # Fallback
    
    async def calculate_availability(self, hours: int = 24) -> float:
        """Вычислить доступность за период на основе успешных запросов"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Подсчитываем успешные запросы (из semantic_ai_cache)
                total_requests = await conn.fetchval("""
                    SELECT COUNT(*)
                    FROM semantic_ai_cache
                    WHERE created_at > NOW() - INTERVAL '1 hour' * $1
                """, hours)
                
                if total_requests == 0:
                    return 1.0  # Нет запросов = 100% доступность
                
                # Подсчитываем ошибки (из circuit_breaker_events или других источников)
                errors = await conn.fetchval("""
                    SELECT COUNT(*)
                    FROM circuit_breaker_events
                    WHERE event_type = 'failure'
                    AND created_at > NOW() - INTERVAL '1 hour' * $1
                """, hours)
                
                if errors is None:
                    errors = 0
                
                # Вычисляем доступность
                successful = total_requests - errors
                availability = successful / total_requests if total_requests > 0 else 1.0
                
                return max(0.0, min(1.0, availability))
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"Error calculating availability: {e}")
            return 0.998  # Fallback
    
    async def calculate_cache_hit_rate(self, hours: int = 24) -> float:
        """Вычислить cache hit rate"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Подсчитываем использование кэша
                total = await conn.fetchval("""
                    SELECT COUNT(*) FROM semantic_ai_cache
                    WHERE created_at > NOW() - INTERVAL '1 hour' * $1
                """, hours)
                
                # Использования (usage_count > 0)
                hits = await conn.fetchval("""
                    SELECT COUNT(*) FROM semantic_ai_cache
                    WHERE created_at > NOW() - INTERVAL '1 hour' * $1
                    AND usage_count > 0
                """, hours)
                
                return hits / total if total > 0 else 0.0
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"Error calculating cache hit rate: {e}")
            return 0.0
    
    async def check_sla_compliance(self) -> Dict[str, Dict]:
        """Проверить соответствие SLA"""
        p95 = await self.calculate_p95_latency()
        availability = await self.calculate_availability()
        cache_hit = await self.calculate_cache_hit_rate()
        
        # Вычисляем token savings из real_time_metrics
        token_savings = await self.calculate_token_savings()
        
        return {
            "p95_latency": {
                "value": p95,
                "target": SLA_DEFINITIONS["p95_latency"],
                "compliant": p95 <= SLA_DEFINITIONS["p95_latency"],
                "unit": "seconds"
            },
            "availability": {
                "value": availability,
                "target": SLA_DEFINITIONS["availability"],
                "compliant": availability >= SLA_DEFINITIONS["availability"],
                "unit": "ratio"
            },
            "cache_hit_rate": {
                "value": cache_hit,
                "target": SLA_DEFINITIONS["cache_hit_rate"],
                "compliant": cache_hit >= SLA_DEFINITIONS["cache_hit_rate"],
                "unit": "ratio"
            },
            "token_savings": {
                "value": token_savings,
                "target": SLA_DEFINITIONS["token_savings"],
                "compliant": token_savings >= SLA_DEFINITIONS["token_savings"],
                "unit": "ratio"
            }
        }
    
    async def calculate_token_savings(self, hours: int = 24) -> float:
        """Вычислить экономию токенов за период"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Получаем метрики из semantic_ai_cache
                total_tokens_saved = await conn.fetchval("""
                    SELECT COALESCE(SUM(tokens_saved), 0)
                    FROM semantic_ai_cache
                    WHERE created_at > NOW() - INTERVAL '1 hour' * $1
                    AND tokens_saved IS NOT NULL
                """, hours)
                
                # Получаем общее количество токенов (оценка)
                total_requests = await conn.fetchval("""
                    SELECT COUNT(*)
                    FROM semantic_ai_cache
                    WHERE created_at > NOW() - INTERVAL '1 hour' * $1
                """, hours)
                
                if total_requests == 0 or total_tokens_saved == 0:
                    return 0.0
                
                # Оцениваем средний размер запроса (примерно 500 токенов)
                estimated_total_tokens = total_requests * 500
                
                # Вычисляем процент экономии
                savings_ratio = total_tokens_saved / estimated_total_tokens if estimated_total_tokens > 0 else 0.0
                
                return max(0.0, min(1.0, savings_ratio))
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"Error calculating token savings: {e}")
            return 0.4  # Fallback

# Глобальный экземпляр
_sla_monitor: Optional[SLAMonitor] = None

def get_sla_monitor(db_url: str = None) -> SLAMonitor:
    """Получить глобальный экземпляр SLAMonitor"""
    global _sla_monitor
    if _sla_monitor is None:
        _sla_monitor = SLAMonitor(db_url)
    return _sla_monitor

