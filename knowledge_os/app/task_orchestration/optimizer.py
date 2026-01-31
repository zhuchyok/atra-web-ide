"""
OrchestrationOptimizer - автоматическая оптимизация на основе метрик A/B.

Анализирует метрики V2 vs existing и предлагает/применяет настройки
(порог декомпозиции, балансировка экспертов, приоритет моделей).
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class OrchestrationOptimizer:
    """Автоматическая оптимизация оркестрации на основе метрик."""

    def __init__(self):
        self._suggestions: list = []

    async def optimize_based_on_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Анализ метрик и формирование рекомендаций (и опционально применение).
        metrics: результат ABMetricsCollector.calculate_comparison() или аналог.
        """
        self._suggestions = []
        comparison = metrics.get("comparison", metrics)
        v2 = metrics.get("v2", {})
        existing = metrics.get("existing", {})

        # 1. Рекомендация по проценту трафика V2
        success_diff = (comparison.get("success_rate_difference") or 0) * 100
        if success_diff > 20 and (v2.get("total_tasks") or 0) >= 5:
            self._suggestions.append({
                "type": "increase_v2_percentage",
                "reason": f"V2 success rate +{success_diff:.1f}% vs existing",
                "current": float(os.getenv("ORCHESTRATION_V2_PERCENTAGE", "10")),
                "suggested": min(100, float(os.getenv("ORCHESTRATION_V2_PERCENTAGE", "10")) + 20),
            })
        elif success_diff < -10 and (v2.get("total_tasks") or 0) >= 5:
            self._suggestions.append({
                "type": "decrease_v2_percentage",
                "reason": f"V2 success rate {success_diff:.1f}% below existing",
                "current": float(os.getenv("ORCHESTRATION_V2_PERCENTAGE", "10")),
                "suggested": max(0, float(os.getenv("ORCHESTRATION_V2_PERCENTAGE", "10")) - 10),
            })

        # 2. Порог декомпозиции (если простые задачи в V2 выполняются долго)
        v2_by_complexity = (v2.get("by_complexity") or {}).get("simple", {})
        simple_avg = v2_by_complexity.get("avg_duration", 0)
        if simple_avg > 30 and (v2.get("total_tasks") or 0) >= 3:
            self._suggestions.append({
                "type": "raise_decomposition_threshold",
                "reason": f"V2 simple tasks avg duration {simple_avg:.0f}s > 30s",
                "suggested_threshold": 0.7,
            })

        return {"suggestions": self._suggestions, "applied": []}

    def get_suggestions(self) -> list:
        return list(self._suggestions)

    async def update_config(self, key: str, value: Any) -> bool:
        """Обновить конфигурацию (env / файл). По умолчанию только логируем."""
        logger.info("OrchestrationOptimizer: would update config %s = %s", key, value)
        return False
