import logging
import time
from collections import deque
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Мировые практики (Netflix Hystrix, resilience4j, Microsoft Polly):
# Ошибки должны «стареть» по времени, а не только по количеству запросов.
# Иначе после серии сбоев без новых запросов monitor навсегда блокирует MLX (deadlock).
# Решение: sliding time window — только события из последних window_seconds считаются.
# После window_seconds тишины старые ошибки выпадают → health_score восстанавливается сам.


class MLXMonitor:
    def __init__(self, window_size: int = 20, window_seconds: int = 120):
        self.window_size = window_size
        # Временное окно по мотивам Hystrix rolling window (по умолчанию 120с = recovery_timeout CB)
        self.window_seconds = window_seconds
        self.tbt_history = deque(maxlen=window_size)
        self.ttft_history = deque(maxlen=window_size)
        self.tps_history = deque(maxlen=window_size)
        # Хранит (timestamp, success) вместо просто bool — для time-based sliding window
        # maxlen=500: при MAX_CONCURRENT=10 и быстрых задачах за 120с макс ~240 событий
        self._timed_history: deque[Tuple[float, bool]] = deque(maxlen=500)
        self.queue_depth = 0
        self.reachable = True

    # Backward compat: внешний код читает success_history через is_overloaded/get_health_score
    @property
    def success_history(self):
        """Совместимость: возвращает только булы из текущего окна."""
        return [ok for _, ok in self._recent_history()]

    def report_metrics(self, ttft: float, tbt: float, tps: float):
        """Report metrics for a single request."""
        self.ttft_history.append(ttft)
        self.tbt_history.append(tbt)
        self.tps_history.append(tps)

    def record_success(self):
        """Record a successful request."""
        self._timed_history.append((time.monotonic(), True))
        self.reachable = True

    def record_failure(self):
        """Record a failed request."""
        self._timed_history.append((time.monotonic(), False))

    def update_queue_depth(self, depth: int):
        """Update the current queue depth."""
        self.queue_depth = depth

    def set_reachable(self, reachable: bool):
        """Explicitly set reachability status."""
        self.reachable = reachable

    def _recent_history(self):
        """Только события из последних window_seconds (sliding window как у Hystrix)."""
        cutoff = time.monotonic() - self.window_seconds
        return [(ts, ok) for ts, ok in self._timed_history if ts >= cutoff]

    def get_health_score(self) -> float:
        """
        Returns a health score from 0.0 (Dead) to 1.0 (Healthy).
        Logic:
        - If not reachable, score = 0.
        - If TBT > 200ms, reduce score.
        - If Queue Depth > 5, reduce score.
        - Error Rate только в пределах window_seconds — старые ошибки не блокируют навсегда.
        """
        if not self.reachable:
            return 0.0

        score = 1.0

        # TBT Penalty: reduce by 0.1 for every 100ms over 200ms, max 0.5 reduction
        if self.tbt_history:
            avg_tbt = sum(self.tbt_history) / len(self.tbt_history)
            if avg_tbt > 0.2:
                penalty = min(0.5, (avg_tbt - 0.2) * 1.0)
                score -= penalty

        # Queue Depth Penalty: reduce by 0.1 for every request over 5, max 0.5 reduction
        if self.queue_depth > 5:
            penalty = min(0.5, (self.queue_depth - 5) * 0.1)
            score -= penalty

        # Error Rate Penalty: только по событиям в sliding window
        recent = self._recent_history()
        if recent:
            error_rate = 1.0 - (sum(ok for _, ok in recent) / len(recent))
            score -= error_rate

        return max(0.0, score)

    def is_overloaded(self) -> bool:
        """Check if MLX is considered overloaded based on health score."""
        return self.get_health_score() < 0.7

    def is_mlx_available(self) -> bool:
        """
        Check if MLX is available (score > 0).
        Благодаря sliding window: после window_seconds без запросов старые ошибки
        выпадают из окна → score восстанавливается → дедлок невозможен.
        """
        return self.get_health_score() > 0.0


_monitor = None


def get_mlx_monitor() -> MLXMonitor:
    global _monitor
    if _monitor is None:
        _monitor = MLXMonitor()
    return _monitor
