"""
[SINGULARITY 10.0] Architecture Profiler.
Collects function-level metrics for core modules to identify optimization hot spots.
"""

import asyncio
import functools
import inspect
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

try:
    import asyncpg
except ImportError:
    asyncpg = None

logger = logging.getLogger(__name__)


class ArchitectureProfiler:
    """Tracks execution time, memory, and success rates of core functions."""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.getenv(
            "DATABASE_URL",
            "postgresql://admin:secret@localhost:6432/knowledge_os",  # pragma: allowlist secret
        )
        self._pool = None

    async def get_pool(self):
        if self._pool is None and asyncpg:
            try:
                self._pool = await asyncpg.create_pool(self.db_url, min_size=1, max_size=20)
            except Exception as e:
                logger.error(f"Failed to create profiler DB pool: {e}")
        return self._pool

    async def log_metric(
        self,
        module_name: str,
        function_name: str,
        execution_time_ms: float,
        success: bool,
        metadata: Optional[dict[str, Any]] = None,
    ):
        """Log a single function execution metric to the database."""
        pool = await self.get_pool()
        if not pool:
            return

        try:
            async with pool.acquire() as conn:
                # Ensure table exists
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS architecture_performance_log (
                        id SERIAL PRIMARY KEY,
                        module_name TEXT NOT NULL,
                        function_name TEXT NOT NULL,
                        execution_time_ms FLOAT NOT NULL,
                        success BOOLEAN NOT NULL,
                        metadata JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_arch_perf_module_func ON architecture_performance_log(module_name, function_name);
                """)

                await conn.execute(
                    """
                    INSERT INTO architecture_performance_log (module_name, function_name, execution_time_ms, success, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                """,
                    module_name,
                    function_name,
                    execution_time_ms,
                    success,
                    metadata,
                )
        except Exception as e:
            logger.debug(f"Profiler failed to log metric: {e}")

    async def get_hot_spots(self, limit: int = 5) -> list[dict[str, Any]]:
        """Identify actionable hotspots (exclude LLM-wait outliers / tiny samples)."""
        pool = await self.get_pool()
        if not pool:
            return []

        # ai_core wrappers often log wall-clock including LLM waits (~hours) — not code bugs.
        max_avg_ms = float(os.getenv("ARCH_HOTSPOT_MAX_AVG_MS", "60000"))
        min_avg_ms = float(os.getenv("ARCH_HOTSPOT_MIN_AVG_MS", "20"))
        min_calls = max(3, int(os.getenv("ARCH_HOTSPOT_MIN_CALLS", "10")))
        max_sample_ms = float(os.getenv("ARCH_HOTSPOT_MAX_SAMPLE_MS", "120000"))
        exclude_modules = {
            m.strip()
            for m in os.getenv("ARCH_HOTSPOT_EXCLUDE_MODULES", "ai_core").split(",")
            if m.strip()
        }

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        module_name,
                        function_name,
                        AVG(execution_time_ms) as avg_time,
                        COUNT(*) as call_count,
                        COUNT(*) FILTER (WHERE success = false) as failure_count
                    FROM architecture_performance_log
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                      AND execution_time_ms > 0
                      AND execution_time_ms < $2
                    GROUP BY module_name, function_name
                    HAVING AVG(execution_time_ms) BETWEEN $3 AND $4
                       AND COUNT(*) >= $5
                    ORDER BY AVG(execution_time_ms) * LN(COUNT(*) + 1) DESC
                    LIMIT $1
                """,
                    limit * 3,  # overfetch then filter excluded modules in Python
                    max_sample_ms,
                    min_avg_ms,
                    max_avg_ms,
                    min_calls,
                )
                spots = []
                for r in rows:
                    d = dict(r)
                    if str(d.get("module_name") or "") in exclude_modules:
                        continue
                    spots.append(d)
                    if len(spots) >= limit:
                        break
                return spots
        except Exception as e:
            logger.error(f"Failed to get hot spots: {e}")
            return []


def profile_function(module_name: str):
    """Decorator to profile sync/async functions."""

    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            success = True
            try:
                return await func(*args, **kwargs)
            except Exception:
                success = False
                raise
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                profiler = get_profiler()
                asyncio.create_task(
                    profiler.log_metric(module_name, func.__name__, duration_ms, success)
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            success = True
            try:
                return func(*args, **kwargs)
            except Exception:
                success = False
                raise
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                profiler = get_profiler()
                # For sync functions, we use a thread-safe way or just fire and forget if in event loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(
                            profiler.log_metric(module_name, func.__name__, duration_ms, success)
                        )
                except RuntimeError:
                    pass  # Not in event loop

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


_profiler_instance = None


def get_profiler() -> ArchitectureProfiler:
    global _profiler_instance
    if _profiler_instance is None:
        _profiler_instance = ArchitectureProfiler()
    return _profiler_instance
