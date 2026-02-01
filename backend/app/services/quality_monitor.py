"""
Фаза 4, День 5: Advanced Quality Monitor с детекцией аномалий.

Рекомендации SRE (Елена): метрики из реальных источников, алерты по SLO.
Рекомендации QA (Анна): пороги faithfulness/relevance/coherence.
Детекция аномалий: пороги + z-score по последним N прогонам (падение метрик).
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Путь к отчётам (от backend/app/services -> backend/)
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_REPORT_PATH = _BACKEND_DIR / "validation_report.json"
_RESULTS_DIR = _BACKEND_DIR / "validation_results"
_ALERTS_PATH = _BACKEND_DIR / "quality_alerts.json"


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
        """Сбор метрик из validation_report и validation_results (SRE: реальный источник)."""
        out: Dict[str, Any] = {
            "requests_last_minute": 0,
            "avg_response_time_ms": 0,
            "error_rate": 0,
            "cache_hit_rate": 0,
            "faithfulness": 0.0,
            "relevance": 0.0,
            "coherence": 0.0,
            "total_queries": 0,
        }
        if _REPORT_PATH.exists():
            try:
                with open(_REPORT_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                m = data.get("avg_metrics", {})
                out["faithfulness"] = m.get("faithfulness", 0.0)
                out["relevance"] = m.get("relevance", 0.0)
                out["coherence"] = m.get("coherence", 0.0)
                out["total_queries"] = data.get("total_queries", 0)
            except Exception as e:
                logger.debug("QualityMonitor: read report %s", e)
        return out

    def _zscore_anomaly(self, values: List[float], current: float, n_std: float = 2.0) -> bool:
        """Аномалия: текущее значение сильно ниже среднего (ML-подобная детекция)."""
        if not values or len(values) < 3:
            return False
        import statistics
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        if stdev < 1e-6:
            return current < mean and mean > 0.5
        z = (current - mean) / stdev if stdev else 0
        return z < -n_std

    async def _detect_anomalies(self, metrics: Dict) -> None:
        """Обнаружение аномалий: пороги (QA) + z-score по истории (SRE)."""
        anomalies: List[str] = []
        if metrics.get("avg_response_time_ms", 0) > self.alert_thresholds["response_time_ms"]:
            anomalies.append(
                f"High response time: {metrics['avg_response_time_ms']}ms"
            )
        if metrics.get("error_rate", 0) > self.alert_thresholds["error_rate"]:
            anomalies.append(
                f"High error rate: {metrics['error_rate']:.1%}"
            )
        # Пороги качества (QA)
        if metrics.get("faithfulness", 1) < self.alert_thresholds["faithfulness"]:
            anomalies.append(
                f"Low faithfulness: {metrics.get('faithfulness', 0):.2f}"
            )
        if metrics.get("relevance", 1) < self.alert_thresholds["relevance"]:
            anomalies.append(
                f"Low relevance: {metrics.get('relevance', 0):.2f}"
            )
        if metrics.get("coherence", 1) < self.alert_thresholds["coherence"]:
            anomalies.append(
                f"Low coherence: {metrics.get('coherence', 0):.2f}"
            )
        # Z-score по последним прогонам (падение метрик)
        hist_rel = [b.get("metrics", {}).get("relevance", 0) for b in self.metrics_buffer[-10:] if b.get("metrics", {}).get("relevance") is not None]
        hist_faith = [b.get("metrics", {}).get("faithfulness", 0) for b in self.metrics_buffer[-10:] if b.get("metrics", {}).get("faithfulness") is not None]
        cur_rel = metrics.get("relevance")
        cur_faith = metrics.get("faithfulness")
        if cur_rel is not None and self._zscore_anomaly(hist_rel, cur_rel):
            anomalies.append(f"Relevance anomaly (z-score): {cur_rel:.2f}")
        if cur_faith is not None and self._zscore_anomaly(hist_faith, cur_faith):
            anomalies.append(f"Faithfulness anomaly (z-score): {cur_faith:.2f}")
        if anomalies:
            await self._send_alert("Anomalies detected: " + "; ".join(anomalies))
            self._write_alerts_file(anomalies)

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

    def _write_alerts_file(self, anomalies: List[str]) -> None:
        """Запись алертов в файл для дашборда (SRE: runbook, дашборд)."""
        if not _ALERTS_PATH.parent.exists():
            return
        try:
            payload = {
                "updated": datetime.now().isoformat(),
                "alerts": [{"message": m, "severity": "warning"} for m in anomalies],
            }
            with open(_ALERTS_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.debug("QualityMonitor: write alerts %s", e)

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
