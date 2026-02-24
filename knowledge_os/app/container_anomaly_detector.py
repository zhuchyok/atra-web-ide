import logging
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class ContainerAnomalyDetector:
    """
    Анализирует метрики контейнеров и выявляет 'агрессоров'.
    Использует статистические методы (Z-score) для обнаружения аномалий.
    """

    def __init__(self):
        self.history = {}  # {container_name: [cpu_history, mem_history]}
        self.max_history = 20
        self.threshold_z = 3.0  # Порог аномалии (3 сигмы)

    def analyze_metrics(self, metrics_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ищет аномалии в текущем батче метрик."""
        anomalies = []

        for m in metrics_list:
            name = m["name"]
            if name not in self.history:
                self.history[name] = {"cpu": [], "net": []}

            # Обновляем историю
            self.history[name]["cpu"].append(m["cpu_percent"])
            self.history[name]["net"].append(m["net_tx_mb"])

            if len(self.history[name]["cpu"]) > self.max_history:
                self.history[name]["cpu"].pop(0)
                self.history[name]["net"].pop(0)

            # Детекция (только если есть история)
            if len(self.history[name]["cpu"]) >= 5:
                cpu_arr = np.array(self.history[name]["cpu"])
                net_arr = np.array(self.history[name]["net"])

                # Проверка CPU
                cpu_mean = np.mean(cpu_arr)
                cpu_std = np.std(cpu_arr) or 0.1
                cpu_z = (m["cpu_percent"] - cpu_mean) / cpu_std

                # Проверка сетевой активности (агрессор)
                net_mean = np.mean(net_arr)
                net_std = np.std(net_arr) or 0.1
                net_z = (m["net_tx_mb"] - net_mean) / net_std

                severity = None
                reason = ""

                if cpu_z > self.threshold_z and m["cpu_percent"] > 80:
                    severity = "high"
                    reason = f"CPU Spike: {m['cpu_percent']}% (Z={cpu_z:.2f})"
                elif net_z > self.threshold_z and m["net_tx_mb"] > 50:
                    severity = "critical"
                    reason = f"Network Aggressor: {m['net_tx_mb']}MB/s (Z={net_z:.2f})"

                if severity:
                    logger.warning(f"🚨 [ANOMALY] {name}: {reason}")
                    anomalies.append(
                        {
                            "container_name": name,
                            "severity": severity,
                            "reason": reason,
                            "metrics": m,
                        }
                    )

        return anomalies


_detector = None


def get_anomaly_detector():
    global _detector
    if _detector is None:
        _detector = ContainerAnomalyDetector()
    return _detector
