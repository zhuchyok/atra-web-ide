"""
Metrics Collector для сбора реальных метрик производительности системы.
Собирает метрики: токен/секунду, стоимость ответа, температура GPU/CPU, коэффициент сжатия контекста.
"""

import asyncio
import os
import logging
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Database connection
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

@dataclass
class Metric:
    """Структура метрики"""
    name: str
    value: float
    unit: Optional[str] = None
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class MetricsCollector:
    """
    Сборщик метрик производительности системы.
    Собирает и сохраняет метрики в БД для анализа трендов.
    """
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self._metrics_buffer: List[Metric] = []
        self._buffer_size = 10  # Сохраняем метрики батчами
        self._last_save_time = time.time()
        self._save_interval = 30  # Сохраняем каждые 30 секунд
    
    async def collect_tokens_per_second(
        self,
        tokens: int,
        duration_seconds: float,
        source: str
    ) -> None:
        """Собирает метрику токенов в секунду"""
        if duration_seconds <= 0:
            return
        
        tokens_per_second = tokens / duration_seconds
        metric = Metric(
            name="tokens_per_second",
            value=tokens_per_second,
            unit="tokens/s",
            source=source,
            metadata={
                "tokens": tokens,
                "duration_seconds": duration_seconds
            }
        )
        await self._add_metric(metric)
    
    async def collect_cost_per_response(
        self,
        cost_usd: float,
        source: str,
        model_name: Optional[str] = None,
        tokens_used: Optional[int] = None
    ) -> None:
        """Собирает метрику стоимости ответа"""
        metric = Metric(
            name="cost_per_response",
            value=cost_usd,
            unit="USD",
            source=source,
            metadata={
                "model_name": model_name,
                "tokens_used": tokens_used
            }
        )
        await self._add_metric(metric)
    
    async def collect_temperature(
        self,
        temp_celsius: float,
        device_type: str,  # 'cpu' or 'gpu'
        source: str
    ) -> None:
        """Собирает метрику температуры устройства"""
        metric_name = f"{device_type}_temp"
        metric = Metric(
            name=metric_name,
            value=temp_celsius,
            unit="celsius",
            source=source,
            metadata={
                "device_type": device_type
            }
        )
        await self._add_metric(metric)
    
    async def collect_compression_ratio(
        self,
        original_size: int,
        compressed_size: int,
        source: str
    ) -> None:
        """Собирает метрику коэффициента сжатия контекста"""
        if original_size <= 0:
            return
        
        compression_ratio = compressed_size / original_size
        metric = Metric(
            name="compression_ratio",
            value=compression_ratio,
            unit="ratio",
            source=source,
            metadata={
                "original_size": original_size,
                "compressed_size": compressed_size,
                "saved_bytes": original_size - compressed_size
            }
        )
        await self._add_metric(metric)
    
    async def _add_metric(self, metric: Metric):
        """Добавляет метрику в буфер"""
        self._metrics_buffer.append(metric)
        
        # Сохраняем, если буфер заполнен или прошло достаточно времени
        current_time = time.time()
        if (len(self._metrics_buffer) >= self._buffer_size or 
            current_time - self._last_save_time >= self._save_interval):
            await self._flush_metrics()
    
    async def _flush_metrics(self):
        """Сохраняет метрики из буфера в БД"""
        if not self._metrics_buffer or not ASYNCPG_AVAILABLE:
            return
        
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                for metric in self._metrics_buffer:
                    await conn.execute("""
                        INSERT INTO real_time_metrics 
                        (metric_name, metric_value, metric_unit, source, metadata, created_at)
                        VALUES ($1, $2, $3, $4, $5, NOW())
                    """,
                    metric.name, metric.value, metric.unit, metric.source,
                    json.dumps(metric.metadata) if metric.metadata else None)
                
                logger.debug(f"✅ Сохранено {len(self._metrics_buffer)} метрик в БД")
                self._metrics_buffer.clear()
                self._last_save_time = time.time()
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения метрик в БД: {e}")
    
    async def get_metrics_stats(
        self,
        metric_name: str,
        hours: int = 24,
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """Получает статистику по метрике за указанный период"""
        if not ASYNCPG_AVAILABLE:
            return {}
        
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                query = """
                    SELECT 
                        AVG(metric_value) as avg_value,
                        MIN(metric_value) as min_value,
                        MAX(metric_value) as max_value,
                        COUNT(*) as count
                    FROM real_time_metrics
                    WHERE metric_name = $1 
                    AND created_at > NOW() - INTERVAL '1 hour' * $2
                """
                params = [metric_name, hours]
                
                if source:
                    query += " AND source = $3"
                    params.append(source)
                
                row = await conn.fetchrow(query, *params)
                
                if row:
                    return {
                        "avg": float(row['avg_value']) if row['avg_value'] else 0.0,
                        "min": float(row['min_value']) if row['min_value'] else 0.0,
                        "max": float(row['max_value']) if row['max_value'] else 0.0,
                        "count": row['count']
                    }
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики метрик: {e}")
        
        return {}
    
    async def flush(self):
        """Принудительно сохраняет все метрики из буфера"""
        await self._flush_metrics()

# Глобальный экземпляр
_metrics_collector: Optional[MetricsCollector] = None

def get_metrics_collector() -> MetricsCollector:
    """Получить глобальный экземпляр MetricsCollector"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector

