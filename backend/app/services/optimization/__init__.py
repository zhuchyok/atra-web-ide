"""
Auto-Optimizer — проактивная оптимизация производительности.
"""

from app.services.optimization.auto_optimizer import (
    AutoOptimizer,
    OptimizationResult,
    OptimizationStrategy,
    PerformanceMetrics,
)

__all__ = [
    "AutoOptimizer",
    "OptimizationStrategy",
    "PerformanceMetrics",
    "OptimizationResult",
]
