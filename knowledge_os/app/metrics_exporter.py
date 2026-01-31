"""
Metrics Exporter
Экспорт метрик в формате Prometheus для Grafana
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

class MetricsExporter:
    """
    Экспортер метрик в формате Prometheus.
    Предоставляет метрики для Grafana dashboard.
    """
    
    def __init__(self, db_url: str = DB_URL):
        """
        Args:
            db_url: URL базы данных
        """
        self.db_url = db_url
    
    async def export_prometheus_metrics(self) -> str:
        """
        Экспортирует метрики в формате Prometheus.
        
        Returns:
            Строка с метриками в формате Prometheus
        """
        metrics = []
        
        try:
            # 1. Latency метрики (p50, p95, p99)
            latency_metrics = await self._get_latency_metrics()
            metrics.extend(latency_metrics)
            
            # 2. Cache hit rate
            cache_metrics = await self._get_cache_metrics()
            metrics.extend(cache_metrics)
            
            # 3. Token usage и savings
            token_metrics = await self._get_token_metrics()
            metrics.extend(token_metrics)
            
            # 4. Error rate
            error_metrics = await self._get_error_metrics()
            metrics.extend(error_metrics)
            
            # 5. Model performance
            model_metrics = await self._get_model_metrics()
            metrics.extend(model_metrics)
            
            # 6. Request rate
            request_metrics = await self._get_request_metrics()
            metrics.extend(request_metrics)
            
        except Exception as e:
            logger.error(f"❌ [METRICS EXPORTER] Ошибка экспорта метрик: {e}")
            metrics.append(f"# ERROR: {e}")
        
        return "\n".join(metrics)
    
    async def _get_latency_metrics(self) -> List[str]:
        """Получает метрики latency"""
        metrics = []
        
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблицы real_time_metrics
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'real_time_metrics'
                    )
                """)
                
                if not table_exists:
                    return metrics
                
                # Получаем p50, p95, p99 latency за последний час
                stats = await conn.fetchrow("""
                    SELECT 
                        percentile_cont(0.50) WITHIN GROUP (ORDER BY value) as p50,
                        percentile_cont(0.95) WITHIN GROUP (ORDER BY value) as p95,
                        percentile_cont(0.99) WITHIN GROUP (ORDER BY value) as p99
                    FROM real_time_metrics
                    WHERE metric_name = 'latency'
                    AND created_at > NOW() - INTERVAL '1 hour'
                """)
                
                if stats:
                    metrics.append(f"# HELP singularity_latency_seconds Latency in seconds")
                    metrics.append(f"# TYPE singularity_latency_seconds summary")
                    metrics.append(f'singularity_latency_seconds{{quantile="0.5"}} {stats["p50"] or 0}')
                    metrics.append(f'singularity_latency_seconds{{quantile="0.95"}} {stats["p95"] or 0}')
                    metrics.append(f'singularity_latency_seconds{{quantile="0.99"}} {stats["p99"] or 0}')
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"⚠️ [METRICS EXPORTER] Ошибка получения latency метрик: {e}")
        
        return metrics
    
    async def _get_cache_metrics(self) -> List[str]:
        """Получает метрики кэша"""
        metrics = []
        
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблицы semantic_ai_cache
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'semantic_ai_cache'
                    )
                """)
                
                if not table_exists:
                    return metrics
                
                # Получаем cache hit rate за последний час
                stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) FILTER (WHERE usage_count > 0)::float / NULLIF(COUNT(*), 0) as hit_rate
                    FROM semantic_ai_cache
                    WHERE created_at > NOW() - INTERVAL '1 hour'
                """)
                
                if stats and stats['hit_rate']:
                    metrics.append(f"# HELP singularity_cache_hit_rate Cache hit rate")
                    metrics.append(f"# TYPE singularity_cache_hit_rate gauge")
                    metrics.append(f'singularity_cache_hit_rate {stats["hit_rate"]}')
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"⚠️ [METRICS EXPORTER] Ошибка получения cache метрик: {e}")
        
        return metrics
    
    async def _get_token_metrics(self) -> List[str]:
        """Получает метрики токенов"""
        metrics = []
        
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблицы semantic_ai_cache
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'semantic_ai_cache'
                    )
                """)
                
                if not table_exists:
                    return metrics
                
                # Получаем статистику токенов за последний час
                stats = await conn.fetchrow("""
                    SELECT 
                        SUM(tokens_saved) as total_saved,
                        COUNT(*) as total_requests
                    FROM semantic_ai_cache
                    WHERE created_at > NOW() - INTERVAL '1 hour'
                """)
                
                if stats:
                    metrics.append(f"# HELP singularity_tokens_saved_total Total tokens saved")
                    metrics.append(f"# TYPE singularity_tokens_saved_total counter")
                    metrics.append(f'singularity_tokens_saved_total {stats["total_saved"] or 0}')
                    
                    metrics.append(f"# HELP singularity_requests_total Total requests")
                    metrics.append(f"# TYPE singularity_requests_total counter")
                    metrics.append(f'singularity_requests_total {stats["total_requests"] or 0}')
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"⚠️ [METRICS EXPORTER] Ошибка получения token метрик: {e}")
        
        return metrics
    
    async def _get_error_metrics(self) -> List[str]:
        """Получает метрики ошибок"""
        metrics = []
        
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблицы real_time_metrics
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'real_time_metrics'
                    )
                """)
                
                if not table_exists:
                    return metrics
                
                # Получаем error rate за последний час
                stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) FILTER (WHERE value != 200)::float / NULLIF(COUNT(*), 0) as error_rate
                    FROM real_time_metrics
                    WHERE metric_name = 'response_status'
                    AND created_at > NOW() - INTERVAL '1 hour'
                """)
                
                if stats and stats['error_rate'] is not None:
                    metrics.append(f"# HELP singularity_error_rate Error rate")
                    metrics.append(f"# TYPE singularity_error_rate gauge")
                    metrics.append(f'singularity_error_rate {stats["error_rate"]}')
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"⚠️ [METRICS EXPORTER] Ошибка получения error метрик: {e}")
        
        return metrics
    
    async def _get_model_metrics(self) -> List[str]:
        """Получает метрики производительности моделей"""
        metrics = []
        
        # Можно добавить метрики из ml_routing_training_data или других источников
        # Пока возвращаем пустой список
        return metrics
    
    async def _get_request_metrics(self) -> List[str]:
        """Получает метрики запросов"""
        metrics = []
        
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблицы semantic_ai_cache
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'semantic_ai_cache'
                    )
                """)
                
                if not table_exists:
                    return metrics
                
                # Получаем количество запросов за последнюю минуту
                stats = await conn.fetchrow("""
                    SELECT COUNT(*) as requests_per_minute
                    FROM semantic_ai_cache
                    WHERE created_at > NOW() - INTERVAL '1 minute'
                """)
                
                if stats:
                    metrics.append(f"# HELP singularity_requests_per_minute Requests per minute")
                    metrics.append(f"# TYPE singularity_requests_per_minute gauge")
                    metrics.append(f'singularity_requests_per_minute {stats["requests_per_minute"] or 0}')
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"⚠️ [METRICS EXPORTER] Ошибка получения request метрик: {e}")
        
        return metrics

# Singleton instance
_metrics_exporter_instance: Optional[MetricsExporter] = None

def get_metrics_exporter(db_url: str = DB_URL) -> MetricsExporter:
    """Получить singleton экземпляр экспортера метрик"""
    global _metrics_exporter_instance
    if _metrics_exporter_instance is None:
        _metrics_exporter_instance = MetricsExporter(db_url=db_url)
    return _metrics_exporter_instance

