import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import asyncpg
from ai_core import run_smart_agent_async

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PerformanceWatchdog")

# Use direct URL for administrative tasks like CREATE INDEX CONCURRENTLY
DB_URL = os.getenv("POSTGRES_DIRECT_URL", "postgresql://admin:secret@knowledge_postgres:5432/knowledge_os")

class PerformanceWatchdog:
    """
    Stability & Performance Watchdog (v1.1).
    Collects slow queries, analyzes them, and autonomously applies optimizations.
    """

    def __init__(self):
        self.interval = int(os.getenv("WATCHDOG_INTERVAL_SEC", "600"))
        self.slow_query_threshold_ms = float(os.getenv("WATCHDOG_SLOW_THRESHOLD_MS", "500"))
        self.autonomous_enabled = os.getenv("WATCHDOG_AUTONOMOUS", "true").lower() in ("true", "1", "yes")
        self._pool = None

    async def get_pool(self):
        if self._pool is None:
            self._pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5)
        return self._pool

    async def collect_slow_queries(self) -> List[Dict[str, Any]]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            try:
                rows = await conn.fetch("""
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
                """, self.slow_query_threshold_ms)
                return [dict(r) for r in rows]
            except Exception as e:
                logger.error(f"Error collecting slow queries: {e}")
                return []

    async def analyze_query(self, query_data: Dict[str, Any]) -> Optional[str]:
        query_text = query_data['query']
        avg_time = query_data['avg_exec_time_ms']
        
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
КОЛИЧЕСТВО ВЫЗОВОВ: {query_data['calls']}
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
            analysis = await run_smart_agent_async(prompt, expert_name="Игорь", category="performance_audit")
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing query: {e}")
            return None

    async def execute_optimization(self, analysis: str) -> bool:
        """Extract and execute SQL optimization from analysis."""
        if not self.autonomous_enabled:
            return False

        # Extract CREATE INDEX CONCURRENTLY
        match = re.search(r"CREATE INDEX CONCURRENTLY\s+[\w_]+\s+ON\s+[\w_]+\s*\([\w_,\s]+\);", analysis, re.IGNORECASE)
        if not match:
            return False

        sql = match.group(0)
        logger.info(f"🚀 Autonomous optimization detected: {sql}")

        pool = await self.get_pool()
        async with pool.acquire() as conn:
            try:
                # 1. Check if index already exists (simple check)
                idx_name = re.search(r"CREATE INDEX CONCURRENTLY\s+([\w_]+)", sql, re.IGNORECASE).group(1)
                exists = await conn.fetchval("SELECT count(*) FROM pg_indexes WHERE indexname = $1", idx_name)
                if exists:
                    logger.info(f"Index {idx_name} already exists, skipping.")
                    return False

                # 2. Execute optimization
                logger.info(f"Executing: {sql}")
                await conn.execute(sql)
                logger.info(f"✅ Optimization applied successfully: {idx_name}")
                
                # 3. Log to evolution_log
                try:
                    await conn.execute("""
                        INSERT INTO evolution_log (event_type, description, metadata)
                        VALUES ('performance_optimization', $1, $2)
                    """, f"Applied autonomous index: {idx_name}", json.dumps({"sql": sql}))
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
                meta = json.dumps({
                    "source": "performance_watchdog",
                    "query_avg_ms": query_data['avg_exec_time_ms'],
                    "type": "database_optimization"
                })
                await conn.execute("""
                    INSERT INTO knowledge_nodes (content, metadata, confidence_score, source_ref, is_verified)
                    VALUES ($1, $2, 0.9, 'performance_watchdog', true)
                """, content, meta)
            except Exception as e:
                logger.error(f"Error logging hypothesis: {e}")

    async def run_once(self):
        logger.info("--- Watchdog Cycle Start ---")
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

    async def start(self):
        logger.info(f"Performance Watchdog started. Interval: {self.interval}s, Autonomous: {self.autonomous_enabled}")
        while True:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"Error in watchdog loop: {e}")
            await asyncio.sleep(self.interval)

if __name__ == "__main__":
    watchdog = PerformanceWatchdog()
    asyncio.run(watchdog.start())
