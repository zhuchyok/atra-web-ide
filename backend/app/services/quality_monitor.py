"""
Фаза 4, День 7: мониторинг качества в реальном времени.

Периодическая валидация, сбор метрик, алерты при аномалиях.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class QualityMonitor:
    """Мониторинг качества в реальном времени."""

    def __init__(self, config: Optional[Dict] = None) -> None:
        self.config = config or {}
        self.metrics_buffer: List[Dict] = []
        self.alerts: List[Dict] = []
        self.is_monitoring = False
        self._tasks: List[asyncio.Task] = []

        self.alert_thresholds = {
            "faithfulness": 0.7,
            "relevance": 0.75,
            "coherence": 0.7,
            "response_time_ms": 1000,
            "error_rate": 0.05,
        }
        self.alert_thresholds.update(
            self.config.get("alert_thresholds", {})
        )

    async def start_monitoring(self) -> None:
        """Запуск мониторинга качества."""
        self.is_monitoring = True
        logger.info("Starting quality monitoring")

        self._tasks = [
            asyncio.create_task(self._periodic_validation()),
            asyncio.create_task(self._monitor_live_metrics()),
            asyncio.create_task(self._check_alerts()),
        ]

        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            logger.info("Quality monitoring stopped")
        finally:
            self.is_monitoring = False

    def stop_monitoring(self) -> None:
        """Остановка мониторинга."""
        self.is_monitoring = False
        for t in self._tasks:
            if not t.done():
                t.cancel()

    async def _periodic_validation(self) -> None:
        """Периодическая валидация на тестовом наборе."""
        while self.is_monitoring:
            try:
                await asyncio.sleep(6 * 3600)
                logger.info("Running periodic validation")
                # Вызов ValidationPipeline можно внедрить через config
                run_validation = self.config.get("run_validation")
                if run_validation and callable(run_validation):
                    result = await run_validation()
                    if result:
                        metrics = result.get("avg_metrics", {})
                        if metrics.get("faithfulness", 1) < self.alert_thresholds["faithfulness"]:
                            await self._send_alert("Low faithfulness score detected")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in periodic validation: %s", e)

    async def _monitor_live_metrics(self) -> None:
        """Мониторинг метрик в реальном времени."""
        while self.is_monitoring:
            try:
                await asyncio.sleep(60)
                metrics = await self._collect_live_metrics()
                self.metrics_buffer.append({
                    "timestamp": datetime.now().isoformat(),
                    "metrics": metrics,
                })
                if len(self.metrics_buffer) > 1000:
                    self.metrics_buffer = self.metrics_buffer[-1000:]
                await self._detect_anomalies(metrics)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in live metrics monitoring: %s", e)

    async def _collect_live_metrics(self) -> Dict[str, Any]:
        """Сбор метрик в реальном времени (заглушка под Prometheus/логи)."""
        return {
            "requests_last_minute": 0,
            "avg_response_time_ms": 0,
            "error_rate": 0,
            "cache_hit_rate": 0,
        }

    async def _detect_anomalies(self, metrics: Dict) -> None:
        """Обнаружение аномалий в метриках."""
        anomalies: List[str] = []
        if metrics.get("avg_response_time_ms", 0) > self.alert_thresholds["response_time_ms"]:
            anomalies.append(
                f"High response time: {metrics['avg_response_time_ms']}ms"
            )
        if metrics.get("error_rate", 0) > self.alert_thresholds["error_rate"]:
            anomalies.append(
                f"High error rate: {metrics['error_rate']:.1%}"
            )
        if anomalies:
            await self._send_alert("Anomalies detected: " + "; ".join(anomalies))

    async def _check_alerts(self) -> None:
        """Проверка и отправка алертов."""
        while self.is_monitoring:
            try:
                await asyncio.sleep(30)
                while self.alerts:
                    alert = self.alerts.pop(0)
                    logger.warning("QUALITY ALERT: %s", alert)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in check_alerts: %s", e)

    async def _send_alert(self, message: str) -> None:
        """Добавление алерта в очередь."""
        self.alerts.append({
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "severity": "warning",
        })

    def get_status(self) -> Dict[str, Any]:
        """Получение статуса мониторинга."""
        return {
            "is_monitoring": self.is_monitoring,
            "metrics_buffer_size": len(self.metrics_buffer),
            "pending_alerts": len(self.alerts),
            "last_metrics": self.metrics_buffer[-1] if self.metrics_buffer else None,
        }
