"""
Auto-Optimizer — проактивная оптимизация производительности.
Цикл: сбор метрик → анализ → применение стратегий.
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# backend/app/services/optimization/ -> project root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


class OptimizationStrategy(Enum):
    """Стратегии оптимизации."""
    CACHE_TTL_ADJUSTMENT = "cache_ttl_adjustment"
    PRELOAD_FREQUENT_PATTERNS = "preload_frequent_patterns"
    INDEX_OPTIMIZATION = "index_optimization"


@dataclass
class PerformanceMetrics:
    """Метрики производительности за период."""
    timestamp: datetime
    p95_latency: float
    p99_latency: float
    cache_hit_rate: float
    db_query_time_p95: float
    request_volume: int
    error_rate: float = 0.0


@dataclass
class OptimizationResult:
    """Результат оптимизации."""
    strategy: OptimizationStrategy
    applied_at: datetime
    parameters_changed: Dict[str, Any]
    improvement_percentage: Optional[float] = None
    description: str = ""


class AutoOptimizer:
    """Автоматический оптимизатор производительности."""

    def __init__(self):
        self.optimization_history: List[OptimizationResult] = []
        self.is_running = False
        self._ttl_history: List[Dict] = []
        self.thresholds = {
            "latency_p95_warning": 150,
            "latency_p95_critical": 200,
            "cache_hit_rate_low": 50.0,  # %
            "cycle_interval_sec": 300,
        }
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Запуск цикла оптимизации."""
        self.is_running = True
        logger.info("🚀 AutoOptimizer запущен")
        while self.is_running:
            try:
                await self.optimization_cycle()
                await asyncio.sleep(self.thresholds["cycle_interval_sec"])
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("AutoOptimizer cycle error: %s", e)
                await asyncio.sleep(60)

    def stop(self) -> None:
        """Остановка оптимизатора."""
        self.is_running = False

    async def optimization_cycle(self) -> None:
        """Один цикл: сбор метрик → анализ → применение стратегий."""
        logger.info("🔄 Цикл оптимизации")
        metrics = await self._collect_metrics()
        issues = self._analyze_issues(metrics)
        for issue in sorted(issues, key=lambda x: x["priority"], reverse=True):
            if not self.is_running:
                break
            await self._apply_optimization(issue, metrics)
        await self._save_report(metrics)

    async def _collect_metrics(self) -> PerformanceMetrics:
        """Сбор метрик из latency_benchmark, cache stats."""
        p95, p99 = 0.0, 0.0
        benchmark_path = REPO_ROOT / "latency_benchmark.json"
        if benchmark_path.exists():
            try:
                with open(benchmark_path, encoding="utf-8") as f:
                    d = json.load(f)
                p95 = float(d.get("p95_ms", 0))
                p99 = float(d.get("p99_ms", 0))
            except Exception as e:
                logger.debug("Benchmark read: %s", e)

        hit_rate = 0.0
        request_volume = 0
        try:
            from app.services.rag_context_cache import get_cache_monitor
            s = get_cache_monitor().get_stats()
            hit_rate = float(s.get("hit_rate_pct", 0))
            request_volume = int(s.get("total", 0))
        except Exception as e:
            logger.debug("Cache stats: %s", e)

        return PerformanceMetrics(
            timestamp=datetime.now(),
            p95_latency=p95,
            p99_latency=p99,
            cache_hit_rate=hit_rate,
            db_query_time_p95=0.0,
            request_volume=request_volume,
        )

    def _analyze_issues(self, m: PerformanceMetrics) -> List[Dict]:
        """Анализ метрик, выявление проблем."""
        issues = []
        if m.p95_latency > self.thresholds["latency_p95_warning"]:
            priority = 90 if m.p95_latency > self.thresholds["latency_p95_critical"] else 70
            issues.append({
                "strategy": OptimizationStrategy.CACHE_TTL_ADJUSTMENT,
                "priority": priority,
                "parameters": {"latency": m.p95_latency, "hit_rate": m.cache_hit_rate},
                "description": f"Высокая латентность P95: {m.p95_latency:.0f}ms",
            })
        if m.cache_hit_rate < self.thresholds["cache_hit_rate_low"]:
            issues.append({
                "strategy": OptimizationStrategy.PRELOAD_FREQUENT_PATTERNS,
                "priority": 80,
                "parameters": {"hit_rate": m.cache_hit_rate},
                "description": f"Низкий hit rate: {m.cache_hit_rate:.1f}%",
            })
        return issues

    async def _apply_optimization(self, issue: Dict, metrics: PerformanceMetrics) -> None:
        """Применение стратегии."""
        strategy = issue["strategy"]
        try:
            if strategy == OptimizationStrategy.CACHE_TTL_ADJUSTMENT:
                result = await self._optimize_cache_ttl(
                    metrics.p95_latency,
                    metrics.cache_hit_rate,
                )
                if result:
                    self.optimization_history.append(OptimizationResult(
                        strategy=strategy,
                        applied_at=datetime.now(),
                        parameters_changed=result,
                        description=issue["description"],
                    ))
            elif strategy == OptimizationStrategy.PRELOAD_FREQUENT_PATTERNS:
                await self._preload_frequent_patterns()
                self.optimization_history.append(OptimizationResult(
                    strategy=strategy,
                    applied_at=datetime.now(),
                    parameters_changed={"preloaded": True},
                    description=issue["description"],
                ))
        except Exception as e:
            logger.warning("Optimization %s failed: %s", strategy.value, e)

    async def _optimize_cache_ttl(self, latency: float, hit_rate: float) -> Optional[Dict]:
        """Динамическая настройка TTL кэша."""
        try:
            from app.services.rag_context_cache import get_rag_context_cache
            cache = get_rag_context_cache()
        except Exception:
            return None
        current_ttl = cache.get_current_ttl()
        new_ttl = current_ttl
        if latency > 150 and hit_rate < 60:
            new_ttl = min(int(current_ttl * 1.2), 600)
        elif hit_rate > 80 and latency < 100:
            new_ttl = max(int(current_ttl * 0.9), 60)
        if new_ttl != current_ttl:
            cache.set_ttl(new_ttl)
            logger.info("🔄 TTL кэша: %s → %s сек", current_ttl, new_ttl)
            return {"old_ttl": current_ttl, "new_ttl": new_ttl}
        return None

    async def _preload_frequent_patterns(self) -> None:
        """Предзагрузка частых запросов из data/frequent_queries.json."""
        queries_file = REPO_ROOT / "data" / "frequent_queries.json"
        if not queries_file.exists():
            logger.debug("frequent_queries.json не найден")
            return
        try:
            with open(queries_file, encoding="utf-8") as f:
                queries = json.load(f)
        except Exception as e:
            logger.debug("frequent_queries load: %s", e)
            return
        if not isinstance(queries, list):
            return
        try:
            from app.services.knowledge_os import KnowledgeOSClient
            from app.services.rag_light import RAGLightService
        except ImportError:
            return
        try:
            kos = KnowledgeOSClient()
            await kos.connect()
            rag = RAGLightService(knowledge_os=kos)
            preloaded = 0
            for q in queries[:15]:
                try:
                    chunks = await rag.search_chunks(q, limit=3)
                    if chunks and rag.rag_context_cache:
                        await rag.rag_context_cache.save_context(q, chunks, limit=3)
                        preloaded += 1
                except Exception:
                    pass
            await kos.disconnect()
            if preloaded:
                logger.info("📥 Предзагружено %s запросов в RAG кэш", preloaded)
        except Exception as e:
            logger.debug("Preload: %s", e)

    async def _save_report(self, metrics: PerformanceMetrics) -> None:
        """Сохранение отчёта цикла."""
        report_path = REPO_ROOT / "backend" / "auto_optimizer_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = {
                "last_cycle": datetime.now().isoformat(),
                "metrics": {
                    "p95_latency": metrics.p95_latency,
                    "p99_latency": metrics.p99_latency,
                    "cache_hit_rate": metrics.cache_hit_rate,
                },
                "optimizations_count": len(self.optimization_history),
            }
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug("Save report: %s", e)

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Данные для дашборда."""
        return {
            "is_running": self.is_running,
            "optimizations_applied": len(self.optimization_history),
            "last_optimizations": [
                {
                    "strategy": r.strategy.value,
                    "at": r.applied_at.isoformat(),
                    "params": r.parameters_changed,
                }
                for r in self.optimization_history[-10:]
            ],
        }
