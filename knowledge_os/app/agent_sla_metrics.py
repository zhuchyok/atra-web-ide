"""
Per-Agent SLA Metrics (Singularity 31.4)

Предоставляет per-agent Prometheus метрики + SLA report для каждого агента.
Интегрируется с expert_worker.py (process_task) и agent_messaging.py (send_message).
"""

import logging
import os
import threading
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# --- SLA thresholds (конфигурируются через env) ---
SLA_LATENCY_P95_THRESHOLD_SEC = float(os.getenv("SLA_LATENCY_P95_THRESHOLD_SEC", "30"))
SLA_ERROR_RATE_THRESHOLD = float(os.getenv("SLA_ERROR_RATE_THRESHOLD", "0.05"))
SLA_AVAILABILITY_THRESHOLD = float(os.getenv("SLA_AVAILABILITY_THRESHOLD", "0.95"))

# --- Prometheus метрики (только если prometheus_client доступен) ---
try:
    from prometheus_client import Counter, Gauge, Histogram

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    Counter = Histogram = Gauge = None

if _PROMETHEUS_AVAILABLE:
    _agent_task_duration = Histogram(
        "agent_task_duration_seconds",
        "Task execution duration per agent",
        ["agent", "task_type", "status"],
        buckets=[1, 5, 15, 30, 60, 120, 300, 600, 1800],
    )
    _agent_errors_total = Counter(
        "agent_errors_total",
        "Errors per agent",
        ["agent", "error_type"],
    )
    _agent_tasks_processed = Counter(
        "agent_tasks_processed_total",
        "Total tasks processed per agent",
        ["agent", "status"],
    )
    _agent_availability = Gauge(
        "agent_availability",
        "Agent availability (1=up, 0=down)",
        ["agent"],
    )
    _agent_latency_p95 = Gauge(
        "agent_latency_p95_seconds",
        "P95 latency per agent",
        ["agent"],
    )
else:
    _agent_task_duration = _agent_errors_total = _agent_tasks_processed = None
    _agent_availability = _agent_latency_p95 = None


def _record_metric_safe(metric, *args, **kwargs):
    """Record a Prometheus metric, safely wrapped."""
    if not _PROMETHEUS_AVAILABLE or metric is None:
        return
    try:
        if hasattr(metric, "observe"):
            metric.labels(*args, **kwargs).observe(kwargs.pop("value", 1))
        elif hasattr(metric, "set"):
            metric.labels(*args, **kwargs).set(kwargs.pop("value", 1))
        elif hasattr(metric, "inc"):
            metric.labels(*args, **kwargs).inc()
    except Exception as _sla_err:
        logger.debug(
            f"[SLA] Failed to record metric {metric._name if hasattr(metric, '_name') else '?'}: {_sla_err}"
        )


class AgentSLAMetrics:
    """Per-agent SLA метрики: длительность, ошибки, доступность, p95 латентность."""

    def __init__(self):
        self._lock = threading.Lock()
        # rolling window для p95 расчёта: agent -> deque of (timestamp, latency_seconds)
        self._latency_samples: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        # статистика для SLA отчёта: agent -> {tasks, errors, ...}
        self._task_stats: Dict[str, dict] = defaultdict(
            lambda: {
                "tasks_processed": 0,
                "errors": 0,
                "total_latency_ms": 0.0,
                "status": "unknown",
            }
        )

    # ------------------------------------------------------------------
    # Методы для записи метрик
    # ------------------------------------------------------------------

    def record_task_duration(
        self, agent: str, task_type: str, status: str, duration_seconds: float
    ):
        """Record task execution duration to histogram."""
        _record_metric_safe(_agent_task_duration, agent, task_type, status, value=duration_seconds)
        with self._lock:
            stats = self._task_stats[agent]
            stats["tasks_processed"] += 1
            stats["total_latency_ms"] += duration_seconds * 1000

    def record_error(self, agent: str, error_type: str):
        """Increment error counter for an agent."""
        _record_metric_safe(_agent_errors_total, agent, error_type)
        with self._lock:
            self._task_stats[agent]["errors"] += 1

    def record_task_completed(self, agent: str, status: str):
        """Increment task processed counter."""
        _record_metric_safe(_agent_tasks_processed, agent, status)

    def set_availability(self, agent: str, is_up: bool):
        """Set agent availability gauge (1=up, 0=down)."""
        _record_metric_safe(_agent_availability, agent, value=1.0 if is_up else 0.0)

    def record_latency(self, agent: str, latency_seconds: float):
        """Track a latency sample for p95 calculation."""
        with self._lock:
            samples = self._latency_samples[agent]
            samples.append((time.time(), latency_seconds))

    # ------------------------------------------------------------------
    # P95 расчёт
    # ------------------------------------------------------------------

    def _calculate_p95(self, agent: str, since_minutes: float = 60) -> float:
        """Calculate P95 latency from recent samples for a given agent."""
        with self._lock:
            samples = self._latency_samples.get(agent)
            if not samples:
                return 0.0

            cutoff = time.time() - since_minutes * 60
            recent = [s for s in samples if s[0] >= cutoff]
            if not recent:
                return 0.0

            sorted_vals = sorted(s[1] for s in recent)
            idx = int(len(sorted_vals) * 0.95)
            idx = min(idx, len(sorted_vals) - 1)
            return sorted_vals[idx] * 1000  # convert to ms

    # ------------------------------------------------------------------
    # SLA отчёт
    # ------------------------------------------------------------------

    def get_sla_report(self, agent: str, since_minutes: int = 60) -> dict:
        """
        Return SLA report dict for a single agent.

        Returns:
            {
                "agent": str,
                "tasks_processed": int,
                "error_rate": float,
                "avg_latency_ms": float,
                "p95_latency_ms": float,
                "availability": float,
                "status": "healthy" | "degraded" | "critical"
            }
        """
        with self._lock:
            stats = self._task_stats.get(agent, {})
            tasks = stats.get("tasks_processed", 0)
            errors = stats.get("errors", 0)
            total_latency = stats.get("total_latency_ms", 0.0)

        p95_ms = self._calculate_p95(agent, since_minutes)
        error_rate = errors / max(tasks, 1)
        avg_latency_ms = total_latency / max(tasks, 1)

        # availability = 1 - error_rate (inverse of error rate as approximation)
        availability = max(0.0, 1.0 - error_rate)

        # Определяем статус
        if (
            p95_ms < SLA_LATENCY_P95_THRESHOLD_SEC * 1000
            and error_rate < SLA_ERROR_RATE_THRESHOLD
            and availability >= SLA_AVAILABILITY_THRESHOLD
        ):
            status = "healthy"
        elif (
            p95_ms < SLA_LATENCY_P95_THRESHOLD_SEC * 1000 * 2
            and error_rate < SLA_ERROR_RATE_THRESHOLD * 2
            and availability >= SLA_AVAILABILITY_THRESHOLD * 0.9
        ):
            status = "degraded"
        else:
            status = "critical"

        return {
            "agent": agent,
            "tasks_processed": tasks,
            "error_rate": round(error_rate, 4),
            "avg_latency_ms": round(avg_latency_ms, 2),
            "p95_latency_ms": round(p95_ms, 2),
            "availability": round(availability, 4),
            "status": status,
        }

    def check_all_agents(self, agents: List[str]) -> List[dict]:
        """Run SLA check for a list of agents."""
        reports = []
        for agent in agents:
            report = self.get_sla_report(agent)
            reports.append(report)

            # Update Prometheus P95 gauge for each agent
            _record_metric_safe(_agent_latency_p95, agent, value=report["p95_latency_ms"] / 1000.0)
        return reports


# --- Singleton ---

_sla_instance: Optional[AgentSLAMetrics] = None
_sla_instance_lock = threading.Lock()


def get_agent_sla_metrics() -> AgentSLAMetrics:
    """Get (or create) the global AgentSLAMetrics singleton."""
    global _sla_instance
    if _sla_instance is None:
        with _sla_instance_lock:
            if _sla_instance is None:
                _sla_instance = AgentSLAMetrics()
    return _sla_instance
