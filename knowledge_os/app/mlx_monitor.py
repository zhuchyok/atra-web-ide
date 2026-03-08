import logging
import time
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class MLXMonitor:
    def __init__(self, window_size: int = 20):
        self.window_size = window_size
        self.tbt_history = deque(maxlen=window_size)
        self.ttft_history = deque(maxlen=window_size)
        self.tps_history = deque(maxlen=window_size)
        self.success_history = deque(maxlen=window_size)
        self.queue_depth = 0
        self.reachable = True

    def report_metrics(self, ttft: float, tbt: float, tps: float):
        """Report metrics for a single request."""
        self.ttft_history.append(ttft)
        self.tbt_history.append(tbt)
        self.tps_history.append(tps)

    def record_success(self):
        """Record a successful request."""
        self.success_history.append(True)
        self.reachable = True

    def record_failure(self):
        """Record a failed request."""
        self.success_history.append(False)

    def update_queue_depth(self, depth: int):
        """Update the current queue depth."""
        self.queue_depth = depth

    def set_reachable(self, reachable: bool):
        """Explicitly set reachability status."""
        self.reachable = reachable

    def get_health_score(self) -> float:
        """
        Returns a health score from 0.0 (Dead) to 1.0 (Healthy).
        Logic:
        - If not reachable, score = 0.
        - If TBT > 200ms, reduce score.
        - If Queue Depth > 5, reduce score.
        - If Error Rate is high, reduce score.
        """
        if not self.reachable:
            return 0.0

        score = 1.0

        # TBT Penalty: reduce by 0.1 for every 100ms over 200ms, max 0.5 reduction
        if self.tbt_history:
            avg_tbt = sum(self.tbt_history) / len(self.tbt_history)
            if avg_tbt > 0.2:
                penalty = min(0.5, (avg_tbt - 0.2) * 1.0)  # 0.1 per 100ms
                score -= penalty

        # Queue Depth Penalty: reduce by 0.1 for every request over 5, max 0.5 reduction
        if self.queue_depth > 5:
            penalty = min(0.5, (self.queue_depth - 5) * 0.1)
            score -= penalty

        # Error Rate Penalty
        if self.success_history:
            error_rate = 1.0 - (sum(self.success_history) / len(self.success_history))
            score -= error_rate  # Direct reduction by error rate

        return max(0.0, score)

    def is_overloaded(self) -> bool:
        """Check if MLX is considered overloaded based on health score."""
        return self.get_health_score() < 0.7

    def is_mlx_available(self) -> bool:
        """Check if MLX is available (score > 0)."""
        return self.get_health_score() > 0.0


_monitor = None


def get_mlx_monitor() -> MLXMonitor:
    global _monitor
    if _monitor is None:
        _monitor = MLXMonitor()
    return _monitor
