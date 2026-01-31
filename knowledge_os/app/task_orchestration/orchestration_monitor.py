"""
OrchestrationMonitor - сбор метрик оркестрации для Grafana/Prometheus.

Собирает длительности фаз, количество подзадач, назначений экспертов и успешность.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = None

try:
    import logging
    logger = logging.getLogger(__name__)
except Exception:
    pass


@dataclass
class OrchestrationMetrics:
    """Метрики одной задачи оркестрации."""
    task_id: str
    phase_durations: Dict[str, float] = field(default_factory=dict)
    subtasks_created: int = 0
    experts_assigned: int = 0
    models_used: List[str] = field(default_factory=list)
    success: bool = False
    total_duration: float = 0.0
    task_type: str = ""


class OrchestrationMonitor:
    """
    Мониторинг системы оркестрации.
    start_phase / end_phase — замер длительности фаз;
    record_task_completion — фиксация завершения задачи;
    get_metrics_for_grafana / export_to_prometheus — экспорт для Grafana/Prometheus.
    """

    def __init__(self):
        self.metrics: Dict[str, OrchestrationMetrics] = {}
        self._phase_start: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.daily_stats: Dict = {
            "tasks_processed": 0,
            "avg_duration": 0.0,
            "success_rate": 0.0,
            "by_task_type": defaultdict(int),
        }

    def start_phase(self, task_id: str, phase: str) -> None:
        """Начало фазы."""
        self._phase_start[task_id][phase] = time.time()

    def end_phase(self, task_id: str, phase: str) -> None:
        """Конец фазы — сохраняем длительность."""
        if task_id not in self._phase_start or phase not in self._phase_start[task_id]:
            return
        start = self._phase_start[task_id][phase]
        duration = time.time() - start
        if task_id not in self.metrics:
            self.metrics[task_id] = OrchestrationMetrics(task_id=task_id)
        self.metrics[task_id].phase_durations[phase] = round(duration, 3)
        del self._phase_start[task_id][phase]

    def record_task_completion(
        self,
        task_id: str,
        success: bool,
        subtasks: int = 0,
        experts: int = 0,
        models: Optional[List[str]] = None,
        task_type: str = "",
    ) -> None:
        """Запись завершения задачи."""
        if task_id not in self.metrics:
            self.metrics[task_id] = OrchestrationMetrics(task_id=task_id)
        m = self.metrics[task_id]
        m.success = success
        m.subtasks_created = subtasks
        m.experts_assigned = experts
        m.models_used = list(models or [])
        m.task_type = task_type
        m.total_duration = round(sum(m.phase_durations.values()), 3)
        self.daily_stats["tasks_processed"] += 1
        self.daily_stats["by_task_type"][task_type or "unknown"] += 1
        all_durations = [x.total_duration for x in self.metrics.values() if x.total_duration]
        self.daily_stats["avg_duration"] = sum(all_durations) / len(all_durations) if all_durations else 0.0
        successful = sum(1 for x in self.metrics.values() if x.success)
        self.daily_stats["success_rate"] = successful / len(self.metrics) if self.metrics else 0.0

    def get_metrics_for_grafana(self) -> Dict:
        """Метрики в формате для Prometheus/Grafana."""
        n = len(self.metrics)
        phase_names = ["receive", "analyze", "decompose", "strategy", "experts", "check_models", "create_subtasks", "assign_executors"]
        phase_durations = {}
        for p in phase_names:
            vals = [m.phase_durations.get(p, 0) for m in self.metrics.values()]
            phase_durations[p] = sum(vals) / len(vals) if vals else 0.0
        return {
            "orchestration_tasks_total": self.daily_stats["tasks_processed"],
            "orchestration_avg_duration_seconds": self.daily_stats["avg_duration"],
            "orchestration_success_rate": self.daily_stats["success_rate"],
            "orchestration_phase_durations": phase_durations,
            "subtasks_per_task_avg": sum(m.subtasks_created for m in self.metrics.values()) / n if n else 0,
            "experts_per_task_avg": sum(m.experts_assigned for m in self.metrics.values()) / n if n else 0,
        }

    async def export_to_prometheus(self) -> str:
        """Экспорт метрик в текстовый формат Prometheus."""
        metrics = self.get_metrics_for_grafana()
        lines = [
            f"orchestration_tasks_total {metrics['orchestration_tasks_total']}",
            f"orchestration_avg_duration_seconds {metrics['orchestration_avg_duration_seconds']:.2f}",
            f"orchestration_success_rate {metrics['orchestration_success_rate']:.3f}",
        ]
        for phase, duration in metrics["orchestration_phase_durations"].items():
            lines.append(f'orchestration_phase_duration_seconds{{phase="{phase}"}} {duration:.2f}')
        lines.append(f"orchestration_subtasks_per_task_avg {metrics['subtasks_per_task_avg']:.2f}")
        lines.append(f"orchestration_experts_per_task_avg {metrics['experts_per_task_avg']:.2f}")
        return "\n".join(lines)
