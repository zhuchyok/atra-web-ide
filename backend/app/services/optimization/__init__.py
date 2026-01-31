"""
Auto-Optimizer — проактивная оптимизация производительности.
"""
from app.services.optimization.auto_optimizer import (
    AutoOptimizer,
    OptimizationStrategy,
    PerformanceMetrics,
    OptimizationResult,
)

__all__ = [
    "AutoOptimizer",
    "OptimizationStrategy",
    "PerformanceMetrics",
    "OptimizationResult",
]
