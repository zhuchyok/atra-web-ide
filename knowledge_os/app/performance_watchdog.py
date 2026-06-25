import asyncio
import json
import logging
import os
import re
import subprocess
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg
import psutil
from ai_core import run_smart_agent_async

try:
    from app.event_bus import Event, EventType, get_event_bus
    from app.redis_manager import RedisManager
except ImportError:
    from event_bus import Event, EventType, get_event_bus
    from redis_manager import RedisManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PerformanceWatchdog")
_REDIS_MANAGER_SINGLETON = None

# Use direct URL for administrative tasks like CREATE INDEX CONCURRENTLY
DB_URL = os.getenv(
    "POSTGRES_DIRECT_URL", "postgresql://admin:secret@knowledge_postgres:5432/knowledge_os"
)


def _get_redis_manager_singleton():
    global _REDIS_MANAGER_SINGLETON
    if _REDIS_MANAGER_SINGLETON is None:
        _REDIS_MANAGER_SINGLETON = RedisManager()
    return _REDIS_MANAGER_SINGLETON


class PerformanceWatchdog:
    """
    Stability & Performance Watchdog (v1.2).
    Collects slow queries, analyzes them, and autonomously applies optimizations.
    Monitors system load and RAM pressure.
    """

    def __init__(self):
        self.interval = int(os.getenv("WATCHDOG_INTERVAL_SEC", "600"))
        self.system_monitor_interval = 10
        self.slow_query_threshold_ms = float(os.getenv("WATCHDOG_SLOW_THRESHOLD_MS", "500"))
        self.autonomous_enabled = os.getenv("WATCHDOG_AUTONOMOUS", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        self._pool = None
        self._redis = _get_redis_manager_singleton()
        self._event_bus = get_event_bus()
        self._cpu_count = psutil.cpu_count()
        # [SINGULARITY 30.2] RAM Velocity tracking
        self._last_ram_pct = None
        self._last_ram_time = None

    async def get_pool(self):
        if self._pool is None:
            self._pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5)
        return self._pool

    async def monitor_system_resources(self):
        """Monitor CPU load and RAM usage with multi-level Ice Mode."""
        try:
            # 1. Check Load Average (1 min)
            load_1, load_5, load_15 = psutil.getloadavg()
            load_threshold = self._cpu_count * 0.8

            # 2. Check RAM usage and Velocity
            ram = psutil.virtual_memory()
            ram_usage_pct = ram.percent
            current_time = time.time()

            # 2.1 Check Disk usage
            disk = psutil.disk_usage("/")
            disk_usage_pct = disk.percent

            ram_velocity = 0.0
            if self._last_ram_pct is not None and self._last_ram_time is not None:
                dt = current_time - self._last_ram_time
                if dt > 0:
                    ram_velocity = (ram_usage_pct - self._last_ram_pct) / dt  # % per second

            self._last_ram_pct = ram_usage_pct
            self._last_ram_time = current_time

            # [SINGULARITY 30.2] Predictive Ice Mode: if RAM is growing fast (>0.5%/sec), trigger soft ice early
            is_predictive_overload = ram_velocity > 0.5 and ram_usage_pct > 70

            # [SINGULARITY 30.3] More aggressive Hard Ice Mode
            is_soft_overload = (
                load_1 > load_threshold or ram_usage_pct > 75 or is_predictive_overload
            )
            is_hard_overload = ram_usage_pct > 85 or (ram_velocity > 0.8 and ram_usage_pct > 75)
            is_exhausted = ram_usage_pct > 90 or disk_usage_pct > 90

            client = await self._redis.get_client()

            if disk_usage_pct > 90:
                logger.warning(
                    f"🚨 [DISK PRESSURE] Disk usage at {disk_usage_pct}%. Triggering emergency cleanup..."
                )
                try:
                    # Clear DuckDB temp files and distillation cache
                    subprocess.run(["rm", "-rf", "/tmp/duckdb_*"], check=False)
                    subprocess.run(["rm", "-rf", "cache/*"], check=False)
                    logger.info("✅ [DISK PRESSURE] Emergency cleanup completed.")
                except Exception as disk_err:
                    logger.error(f"❌ [DISK PRESSURE] Cleanup failed: {disk_err}")

            if is_hard_overload:
                await client.set("system:ice_mode", "hard", ex=60)
                await client.set("system:throttle_rd_bidding", "1", ex=300)
                await client.set("system:elk_drop_noncritical", "1", ex=300)
                logger.warning(
                    f"❄️ [HARD ICE MODE] RAM={ram_usage_pct}% (v={ram_velocity:.2f}%/s) - Aggressive protection active"
                )
            elif is_soft_overload:
                await client.set("system:ice_mode", "soft", ex=60)
                await client.set("system:elk_drop_noncritical", "1", ex=120)
                logger.info(
                    f"❄️ [SOFT ICE MODE] Load={load_1:.2f}, RAM={ram_usage_pct}% (v={ram_velocity:.2f}%/s) - Throttling active"
                )
            else:
                await client.delete("system:ice_mode")
                await client.delete("system:elk_drop_noncritical")

            # 3. Broadcast RESOURCE_EXHAUSTED if needed
            if is_exhausted or ram_velocity > 1.0:  # Also if growing extremely fast
                event = Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.RESOURCE_EXHAUSTED,
                    payload={
                        "ram_usage_pct": ram_usage_pct,
                        "ram_velocity": ram_velocity,
                        "load_avg": load_1,
                        "reason": "High RAM pressure or rapid growth detected",
                    },
                    source="performance_watchdog",
                )
                await self._event_bus.publish(event)

            # 4. Broadcast PERFORMANCE_DEGRADED for general monitoring
            if is_soft_overload:
                event = Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.PERFORMANCE_DEGRADED,
                    payload={
                        "status": "Throttling",
                        "load_avg": load_1,
                        "ram_usage_pct": ram_usage_pct,
                        "cpu_count": self._cpu_count,
                    },
                    source="performance_watchdog",
                )
                await self._event_bus.publish(event)

        except Exception as e:
            logger.error(f"Error in system resource monitoring: {e}")

    async def evaluate_lane_sla(self):
        """
        Protect distillation lane if throughput drops and backlog is still high.
        Sets system:throttle_rd_bidding to reduce RD contention during degradation.
        """
        try:
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                distilled_15m = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM knowledge_nodes
                    WHERE (metadata->>'distilled_at')::timestamptz > NOW() - INTERVAL '15 minutes'
                    """
                )
                undistilled = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM knowledge_nodes
                    WHERE metadata->>'distilled' IS NULL
                       OR metadata->>'distilled' = 'false'
                    """
                )
                oldest_pending_age_minutes = await conn.fetchval(
                    """
                    SELECT EXTRACT(EPOCH FROM (NOW() - MIN(created_at))) / 60.0
                    FROM tasks
                    WHERE status = 'pending'
                    """
                )
                pending_count = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM tasks
                    WHERE status = 'pending'
                    """
                )

            client = await self._redis.get_client()
            ice_mode = str(await client.get("system:ice_mode") or "").lower()
            degraded = (distilled_15m or 0) == 0 and (undistilled or 0) > 1000
            queue_stale = (oldest_pending_age_minutes or 0) > 30
            under_pressure = ice_mode in ("hard", "soft")

            # Avoid self-deadlock: throttle RD only when the host is under real pressure.
            if degraded and under_pressure:
                await client.set("system:throttle_rd_bidding", "1", ex=300)
                logger.warning(
                    f"🛡️ [SLA] Distillation degraded (15m=0, undistilled={undistilled}, ice={ice_mode or 'none'}). "
                    "RD bidding throttled for 5m."
                )
            else:
                await client.delete("system:throttle_rd_bidding")

            if queue_stale:
                await client.set("system:rebalance_needed", "1", ex=300)
                logger.warning(
                    f"🛡️ [SLA] Pending queue stale ({oldest_pending_age_minutes:.1f}m, count={pending_count}). "
                    "Rebalance flag enabled."
                )
            if not queue_stale:
                await client.delete("system:rebalance_needed")
        except Exception as e:
            logger.error(f"Error evaluating lane SLA: {e}")

    async def reconcile_blackboard(self):
        """Run blackboard reconciliation loop to recover from ownership drifts."""
        try:
            try:
                from app.services.blackboard_service import get_blackboard_service
            except ImportError:
                from services.blackboard_service import get_blackboard_service
            blackboard = get_blackboard_service()
            result = await blackboard.reconcile_goals_with_tasks(stale_minutes=15)
            if result.get("reopened_no_heartbeat") or result.get("reopened_policy_mismatch"):
                logger.warning(f"♻️ [RECONCILE] Blackboard recovered tasks: {result}")
        except Exception as e:
            logger.error(f"Error reconciling blackboard goals: {e}")

    async def collect_slow_queries(self) -> List[Dict[str, Any]]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            try:
                rows = await conn.fetch(
                    """
                    SELECT
                        query,
                        calls,
                        total_exec_time / calls as avg_exec_time_ms,
                        total_exec_time as total_time_ms,
                        rows,
                        shared_blks_hit,
                        shared_blks_read
                    FROM pg_stat_statements
                    WHERE total_exec_time / calls > $1
                      AND query NOT LIKE 'FETCH%'
                      AND query NOT LIKE 'BEGIN%'
                      AND query NOT LIKE 'COMMIT%'
                      AND query NOT LIKE 'ROLLBACK%'
                      AND query NOT LIKE '%pg_stat_statements%'
                    ORDER BY total_exec_time DESC
                    LIMIT 5
                """,
                    self.slow_query_threshold_ms,
                )
                return [dict(r) for r in rows]
            except Exception as e:
                logger.error(f"Error collecting slow queries: {e}")
                return []

    async def analyze_query(self, query_data: Dict[str, Any]) -> Optional[str]:
        query_text = query_data["query"]
        avg_time = query_data["avg_exec_time_ms"]

        explain_plan = "N/A"
        if query_text.strip().upper().startswith("SELECT"):
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                try:
                    plan_rows = await conn.fetch(f"EXPLAIN (ANALYZE, BUFFERS) {query_text}")
                    explain_plan = "\n".join([r[0] for r in plan_rows])
                except Exception as e:
                    explain_plan = f"Could not get EXPLAIN plan: {e}"

        prompt = f"""
Ты - эксперт по производительности PostgreSQL в корпорации ATRA.
Проанализируй медленный запрос и предложи конкретную оптимизацию (индекс).

ЗАПРОС:
{query_text}

СРЕДНЕЕ ВРЕМЯ: {avg_time:.2f} ms
КОЛИЧЕСТВО ВЫЗОВОВ: {query_data["calls"]}
ПЛАН ВЫПОЛНЕНИЯ (EXPLAIN ANALYZE):
{explain_plan}

ОТВЕТЬ В ФОРМАТЕ:
1. ПРИЧИНА: почему запрос медленный.
2. ОПТИМИЗАЦИЯ: конкретный SQL для создания индекса.
3. ОЖИДАЕМЫЙ ЭФФЕКТ: во сколько раз ускорится.

ВАЖНО: Для создания индекса используй ТОЛЬКО этот формат:
CREATE INDEX CONCURRENTLY idx_watchdog_[unique_id] ON table_name (column_name);
"""
        try:
            analysis = await run_smart_agent_async(
                prompt, expert_name="Игорь", category="performance_audit"
            )
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing query: {e}")
            return None

    async def execute_optimization(self, analysis: str) -> bool:
        """Extract and execute SQL optimization from analysis."""
        if not self.autonomous_enabled:
            return False

        # Extract CREATE INDEX CONCURRENTLY
        match = re.search(
            r"CREATE INDEX CONCURRENTLY\s+[\w_]+\s+ON\s+[\w_]+\s*\([\w_,\s]+\);",
            analysis,
            re.IGNORECASE,
        )
        if not match:
            return False

        sql = match.group(0)
        logger.info(f"🚀 Autonomous optimization detected: {sql}")

        pool = await self.get_pool()
        async with pool.acquire() as conn:
            try:
                # 1. Check if index already exists (simple check)
                idx_name = re.search(
                    r"CREATE INDEX CONCURRENTLY\s+([\w_]+)", sql, re.IGNORECASE
                ).group(1)
                exists = await conn.fetchval(
                    "SELECT count(*) FROM pg_indexes WHERE indexname = $1", idx_name
                )
                if exists:
                    logger.info(f"Index {idx_name} already exists, skipping.")
                    return False

                # 2. Execute optimization
                logger.info(f"Executing: {sql}")
                await conn.execute(sql)
                logger.info(f"✅ Optimization applied successfully: {idx_name}")

                # 3. Log to evolution_log
                try:
                    await conn.execute(
                        """
                        INSERT INTO evolution_log (event_type, description, metadata)
                        VALUES ('performance_optimization', $1, $2)
                    """,
                        f"Applied autonomous index: {idx_name}",
                        json.dumps({"sql": sql}),
                    )
                except:
                    pass

                return True
            except Exception as e:
                logger.error(f"❌ Error applying optimization: {e}")
                return False

    async def log_optimization_hypothesis(self, query_data: Dict[str, Any], analysis: str):
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            try:
                content = f"🚀 PERFORMANCE HYPOTHESIS\nQuery: {query_data['query'][:500]}\n\nAnalysis:\n{analysis}"
                meta = json.dumps(
                    {
                        "source": "performance_watchdog",
                        "query_avg_ms": query_data["avg_exec_time_ms"],
                        "type": "database_optimization",
                    }
                )
                await conn.execute(
                    """
                    INSERT INTO knowledge_nodes (content, metadata, confidence_score, source_ref, is_verified)
                    VALUES ($1, $2, 0.9, 'performance_watchdog', true)
                """,
                    content,
                    meta,
                )
            except Exception as e:
                logger.error(f"Error logging hypothesis: {e}")

    async def run_once(self):
        logger.info("--- Watchdog Cycle Start ---")

        # [SINGULARITY 29.1] Infrastructure Self-Healing
        await self.check_and_heal_containers()
        await self.evaluate_lane_sla()
        await self.reconcile_blackboard()

        # [SINGULARITY 30.4] Z-Cleaner: Proactive Cache Clearing in Ice Mode
        try:
            client = await self._redis.get_client()
            ice_mode = await client.get("system:ice_mode")
            if ice_mode:
                logger.warning("❄️ [Z-CLEANER] Ice Mode active. Triggering proactive cleanup...")
                import ctypes
                import ctypes.util
                import gc

                gc.collect()
                try:
                    libc = ctypes.CDLL(ctypes.util.find_library("c"))
                    libc.malloc_trim(0)
                except:
                    pass

                # Clear Ollama cache for non-immortal models
                try:
                    from app.model_memory_manager import get_memory_manager

                    mmm = get_memory_manager()
                    await mmm.emergency_memory_cleanup()
                except:
                    pass
        except Exception as z_err:
            logger.error(f"❌ [Z-CLEANER] Cleanup failed: {z_err}")

        # [SINGULARITY 29.2] Blackboard GC
        try:
            from services.blackboard_service import get_blackboard_service

            bb = get_blackboard_service()
            reclaimed = await bb.run_gc_cycle()
            if reclaimed > 0:
                try:
                    from services.notification_service import get_notification_service

                    notifier = get_notification_service()
                    await notifier.notify(
                        "🧹 Blackboard GC Reclaim",
                        f"Reclaimed {reclaimed} abandoned tasks from Blackboard.",
                        priority="high",
                        tags=["recycle", "robot"],
                    )
                except:
                    pass
        except Exception as gc_err:
            logger.error(f"❌ [WATCHDOG] Blackboard GC failed: {gc_err}")

        slow_queries = await self.collect_slow_queries()

        if not slow_queries:
            logger.info("No slow queries detected.")
            return

        for q in slow_queries:
            analysis = await self.analyze_query(q)
            if analysis:
                await self.log_optimization_hypothesis(q, analysis)
                # Autonomous Action
                await self.execute_optimization(analysis)

        logger.info("--- Watchdog Cycle End ---")

    async def check_and_heal_containers(self):
        """[SINGULARITY 29.1] Check critical containers and restart if exited."""
        critical_containers = [
            "atra-web-ide-gateway",
            "knowledge_os_redis",
            "knowledge_postgres",
            "expert-worker-heavy",
        ]

        for container in critical_containers:
            try:
                # Check status
                result = subprocess.run(
                    ["docker", "inspect", "-f", "{{.State.Status}}", container],
                    capture_output=True,
                    text=True,
                )
                status = result.stdout.strip()

                if status in ("exited", "dead", "paused"):
                    logger.warning(
                        f"🚨 [SELF-HEALING] Container {container} is {status}! Attempting to restart..."
                    )
                    subprocess.run(["docker", "start", container], check=True)
                    logger.info(f"✅ [SELF-HEALING] Container {container} restarted successfully.")

                    # [SINGULARITY 29.3] Notify via ntfy
                    try:
                        from services.notification_service import get_notification_service

                        notifier = get_notification_service()
                        await notifier.notify(
                            f"🚨 Контейнер {status.upper()}",
                            f"Контейнер {container} был в состоянии {status}. Успешно перезапущен.",
                            priority="urgent",
                            tags=["emergency", "muscle"],
                        )
                    except:
                        pass

                elif status == "running":
                    # Optional: check health if available
                    health_res = subprocess.run(
                        ["docker", "inspect", "-f", "{{.State.Health.Status}}", container],
                        capture_output=True,
                        text=True,
                    )
                    health = health_res.stdout.strip()
                    if health == "unhealthy":
                        logger.warning(
                            f"🚑 [SELF-HEALING] Container {container} is UNHEALTHY! Forcing restart..."
                        )
                        subprocess.run(["docker", "restart", container], check=True)

                        # [SINGULARITY 29.3] Notify via ntfy
                        try:
                            from services.notification_service import get_notification_service

                            notifier = get_notification_service()
                            await notifier.notify(
                                "🚑 Контейнер НЕЗДОРОВ",
                                f"Контейнер {container} был нездоров. Применен принудительный перезапуск.",
                                priority="high",
                                tags=["ambulance", "wrench"],
                            )
                        except:
                            pass
            except Exception as e:
                logger.error(f"❌ [SELF-HEALING] Failed to check/heal {container}: {e}")

    async def start(self):
        logger.info(
            f"Performance Watchdog started. Interval: {self.interval}s, Autonomous: {self.autonomous_enabled}"
        )

        # Start system monitoring task
        asyncio.create_task(self.system_monitor_loop())

        while True:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"Error in watchdog loop: {e}")
            await asyncio.sleep(self.interval)

    async def system_monitor_loop(self):
        """Loop for monitoring system resources every 10 seconds."""
        logger.info(f"System monitoring loop started. Interval: {self.system_monitor_interval}s")
        while True:
            try:
                await self.monitor_system_resources()
            except Exception as e:
                logger.error(f"Error in system monitor loop: {e}")
            await asyncio.sleep(self.system_monitor_interval)


if __name__ == "__main__":
    watchdog = PerformanceWatchdog()
    asyncio.run(watchdog.start())
