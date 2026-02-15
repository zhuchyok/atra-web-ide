import docker
import asyncio
import logging
import time
from typing import Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class ContainerMetricsCollector:
    """
    Собирает метрики производительности Docker-контейнеров в реальном времени.
    Основа для кросс-контейнерной самодиагностики.
    """
    def __init__(self):
        try:
            self.client = docker.from_env()
            logger.info("✅ MetricsCollector: Подключен к Docker")
        except Exception as e:
            self.client = None
            logger.error(f"❌ MetricsCollector: Ошибка Docker: {e}")

    async def collect_all_metrics(self) -> List[Dict[str, Any]]:
        """Собирает статистику по всем активным контейнерам."""
        if not self.client: return []
        
        metrics = []
        containers = self.client.containers.list()
        
        for container in containers:
            try:
                # Получаем один снимок статистики (не стрим)
                stats = container.stats(stream=False)
                
                # Расчет CPU % (стандартная формула Docker)
                cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                            stats['precpu_stats']['cpu_usage']['total_usage']
                system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                               stats['precpu_stats']['system_cpu_usage']
                
                cpu_percent = 0.0
                if system_delta > 0.0 and cpu_delta > 0.0:
                    cpu_percent = (cpu_delta / system_delta) * len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100.0

                # Память
                mem_usage = stats['memory_stats'].get('usage', 0)
                mem_limit = stats['memory_stats'].get('limit', 1)
                mem_percent = (mem_usage / mem_limit) * 100.0

                # Сеть
                net_io = stats.get('networks', {})
                rx_bytes = sum(iface['rx_bytes'] for iface in net_io.values())
                tx_bytes = sum(iface['tx_bytes'] for iface in net_io.values())

                metrics.append({
                    "container_id": container.id[:12],
                    "name": container.name,
                    "cpu_percent": round(cpu_percent, 2),
                    "memory_usage_mb": round(mem_usage / (1024 * 1024), 2),
                    "memory_percent": round(mem_percent, 2),
                    "net_rx_mb": round(rx_bytes / (1024 * 1024), 2),
                    "net_tx_mb": round(tx_bytes / (1024 * 1024), 2),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                logger.debug(f"Ошибка сбора метрик для {container.name}: {e}")
                
        return metrics

    async def start_monitoring_loop(self, interval: int = 30):
        """Фоновый цикл публикации метрик в EventBus."""
        while True:
            metrics = await self.collect_all_metrics()
            if metrics:
                try:
                    from app.event_bus import get_event_bus, Event, EventType
                    event_bus = get_event_bus()
                    await event_bus.publish(Event(
                        event_type="CONTAINER_METRICS",
                        payload={"metrics": metrics},
                        source="metrics_collector"
                    ))
                except ImportError:
                    logger.debug("EventBus недоступен, метрики только в логах")
            
            await asyncio.sleep(interval)

_collector = None
def get_metrics_collector():
    global _collector
    if _collector is None:
        _collector = ContainerMetricsCollector()
    return _collector
