"""
Метрики рекомендаций перехода в режим Агент (Фаза 2, день 3–4).
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List
from collections import defaultdict


@dataclass
class AgentSuggestionMetric:
    query: str
    suggested: bool
    complexity_score: float
    reason: str
    user_action: str = "unknown"  # "accepted", "ignored", "switched"
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class AgentSuggestionMetrics:
    """Метрики для рекомендаций Agent (in-memory)."""

    def __init__(self):
        self.metrics: List[AgentSuggestionMetric] = []
        self.suggestion_stats = defaultdict(int)

    def add_suggestion(self, metric: AgentSuggestionMetric):
        """Добавление метрики рекомендации."""
        self.metrics.append(metric)
        self.suggestion_stats["total"] += 1
        if metric.suggested:
            self.suggestion_stats["suggested"] += 1
        else:
            self.suggestion_stats["not_suggested"] += 1
        if metric.user_action != "unknown":
            self.suggestion_stats[metric.user_action] += 1

    def get_stats(self) -> Dict:
        """Статистика рекомендаций."""
        if not self.metrics:
            return {"total": 0}
        suggested_metrics = [m for m in self.metrics if m.suggested]
        stats = {
            "total_queries": len(self.metrics),
            "suggested_count": len(suggested_metrics),
            "suggestion_rate": len(suggested_metrics) / len(self.metrics),
            "user_actions": dict(self.suggestion_stats),
        }
        if suggested_metrics:
            avg_score = sum(m.complexity_score for m in suggested_metrics) / len(suggested_metrics)
            stats["avg_complexity_score"] = round(avg_score, 2)
            reasons = defaultdict(int)
            for m in suggested_metrics:
                if m.reason:
                    reasons[m.reason] += 1
            stats["top_reasons"] = sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:5]
        return stats


agent_suggestion_metrics = AgentSuggestionMetrics()
