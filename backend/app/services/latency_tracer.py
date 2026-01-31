"""
Трассировка latency по этапам (Фаза 4.1).
Цель: P95 < 300ms для режима Ask.
"""
import time
import logging
from contextlib import contextmanager
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class LatencySpan:
    """Этап трассировки."""
    name: str
    start_time: float
    end_time: float = 0.0
    metadata: Dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000


class LatencyTracer:
    """Трассировщик latency по этапам."""

    def __init__(self):
        self.spans: List[LatencySpan] = []
        self.current_trace_id: Optional[str] = None

    @contextmanager
    def measure(self, name: str, metadata: Optional[Dict] = None):
        """Контекстный менеджер для измерения времени."""
        span = LatencySpan(
            name=name,
            start_time=time.time(),
            metadata=metadata or {},
        )
        try:
            yield span
        finally:
            span.end_time = time.time()
            self.spans.append(span)
            if span.duration_ms > 50:
                logger.debug("Slow span '%s': %.1fms", name, span.duration_ms)

    def start_trace(self, trace_id: str):
        """Начало новой трассировки."""
        self.current_trace_id = trace_id
        self.spans = []

    def get_trace_summary(self) -> Dict:
        """Сводка по текущей трассировке."""
        if not self.spans:
            return {}
        total_ms = sum(s.duration_ms for s in self.spans)
        return {
            "trace_id": self.current_trace_id,
            "total_ms": total_ms,
            "spans": [
                {"name": s.name, "duration_ms": s.duration_ms, "metadata": s.metadata}
                for s in self.spans
            ],
            "bottlenecks": self._identify_bottlenecks(),
            "timestamp": datetime.now().isoformat(),
        }

    def _identify_bottlenecks(self) -> List[Dict]:
        """Этапы, занимающие >20% времени."""
        if not self.spans:
            return []
        total = sum(s.duration_ms for s in self.spans)
        if total <= 0:
            return []
        result = []
        for s in self.spans:
            pct = (s.duration_ms / total) * 100
            if pct > 20:
                result.append({
                    "span": s.name,
                    "duration_ms": s.duration_ms,
                    "percentage": pct,
                    "metadata": s.metadata,
                })
        return sorted(result, key=lambda x: x["percentage"], reverse=True)


# Глобальный трассировщик
latency_tracer = LatencyTracer()
