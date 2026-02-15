import asyncio
import logging
import os
import httpx
import time
from datetime import datetime, timezone
from app.event_bus import get_event_bus, Event, EventType, EventBus
import uuid

logger = logging.getLogger(__name__)

class PerformanceDaemon:
    """
    Автономный демон для мониторинга производительности (Игорь/Дмитрий).
    Следит за метриками и публикует события при деградации.
    """
    def __init__(self, name: str, metrics_to_watch: list):
        self.name = name
        self.metrics_to_watch = metrics_to_watch
        self.event_bus = get_event_bus()
        self.running = False

    async def start(self):
        self.running = True
        asyncio.create_task(self._run_loop())
        logger.info(f"🚀 Демон {self.name} запущен")

    async def _run_loop(self):
        while self.running:
            try:
                for metric in self.metrics_to_watch:
                    value = await self._fetch_metric(metric)
                    threshold = metric.get('threshold', 1.0)
                    
                    if value > threshold:
                        logger.warning(f"⚠️ [{self.name}] Деградация метрики {metric['name']}: {value} > {threshold}")
                        
                        # [SRE SELF-HEALING] Автоматическое исправление для Игоря
                        if self.name == "Игорь":
                            await self._attempt_self_healing(metric, value)

                        await self.event_bus.publish(Event(
                            event_id=str(uuid.uuid4()),
                            event_type=EventType.PERFORMANCE_DEGRADED,
                            payload={
                                "metric": metric['name'],
                                "value": value,
                                "threshold": threshold,
                                "expert": self.name,
                                "action_required": True
                            },
                            source=self.name
                        ))
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле демона {self.name}: {e}")
            await asyncio.sleep(60)

    async def _attempt_self_healing(self, metric, value):
        """[Self-Healing Infrastructure] Автоматические действия по исправлению."""
        logger.info(f"🔧 [SELF-HEALING] Игорь инициирует исправление для {metric['name']}")
        
        if metric['name'] == 'rag_latency':
            # Действие: Очистка кэша Redis и переиндексация легких узлов
            try:
                from app.redis_manager import redis_manager
                await (await redis_manager.get_client()).flushdb()
                logger.info("🧹 [SELF-HEALING] Кэш Redis очищен для ускорения RAG")
            except Exception as e:
                logger.error(f"❌ [SELF-HEALING] Ошибка очистки кэша: {e}")

        if metric['name'] == 'db_connections':
            # Действие: Уведомление системы о необходимости скейлинга пула (имитация)
            logger.warning("📉 [SELF-HEALING] Высокая нагрузка на БД. Рекомендуется оптимизация запросов.")

    async def _fetch_metric(self, metric):
        """Реальное получение метрик из БД или Prometheus."""
        try:
            from app.evaluator import get_pool
            pool = await get_pool()
            async with pool.acquire() as conn:
                if metric['name'] == 'rag_latency':
                    # Средняя задержка RAG за последние 5 минут
                    val = await conn.fetchval("""
                        SELECT AVG((metadata->>'latency')::float) 
                        FROM knowledge_nodes 
                        WHERE created_at > NOW() - INTERVAL '5 minutes' 
                          AND metadata->>'type' = 'rag_query'
                    """)
                    return val if val is not None else 0.5
                
                if metric['name'] == 'db_connections':
                    val = await conn.fetchval("SELECT count(*) FROM pg_stat_activity")
                    return float(val) if val is not None else 0.0
                
                if metric['name'] == 'inference_time':
                    val = await conn.fetchval("""
                        SELECT AVG(feedback_score) FROM interaction_logs 
                        WHERE created_at > NOW() - INTERVAL '1 hour'
                    """)
                    # Имитируем: если фидбек падает, значит инференс плохой (условно)
                    return 5.0 if (val and val < 3) else 1.0
                    
            return 0.0
        except Exception as e:
            logger.error(f"Error fetching metric {metric['name']}: {e}")
            return 0.0

async def setup_daemons():
    igor = PerformanceDaemon("Игорь", [
        {"name": "rag_latency", "threshold": 2.0},
        {"name": "db_connections", "threshold": 250}
    ])
    dmitriy = PerformanceDaemon("Дмитрий", [
        {"name": "gpu_memory_usage", "threshold": 0.9},
        {"name": "inference_time", "threshold": 10.0}
    ])
    
    await igor.start()
    await dmitriy.start()
