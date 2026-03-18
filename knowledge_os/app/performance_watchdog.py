import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import asyncpg
from ai_core import run_smart_agent_async

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PerformanceWatchdog")

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os")

class PerformanceWatchdog:
    """
    Stability & Performance Watchdog (v1.0).
    Collects slow queries from pg_stat_statements and analyzes them via Victoria.
    """

    def __init__(self):
        self.interval = int(os.getenv("WATCHDOG_INTERVAL_SEC", "600"))  # 10 minutes
        self.slow_query_threshold_ms = float(os.getenv("WATCHDOG_SLOW_THRESHOLD_MS", "500"))
        self._pool = None

    async def get_pool(self):
        if self._pool is None:
            self._pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5)
        return self._pool

    async def collect_slow_queries(self) -> List[Dict[str, Any]]:
        """Collect top 5 slow queries from pg_stat_statements."""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            try:
                # Get queries that take more than threshold on average or in total
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
        """Analyze a slow query using Victoria and suggest optimization."""
        query_text = query_data['query']
        avg_time = query_data['avg_exec_time_ms']
        
        logger.info(f"Analyzing slow query (avg {avg_time:.2f}ms): {query_text[:100]}...")
        
        # Get EXPLAIN plan if possible (for SELECT only to be safe)
        explain_plan = "N/A"
        if query_text.strip().upper().startswith("SELECT"):
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                try:
                    # Use EXPLAIN (FORMAT JSON) for better parsing by LLM
                    plan_rows = await conn.fetch(f"EXPLAIN (ANALYZE, BUFFERS) {query_text}")
                    explain_plan = "\n".join([r[0] for r in plan_rows])
                except Exception as e:
                    explain_plan = f"Could not get EXPLAIN plan: {e}"

        prompt = f"""
Ты - эксперт по производительности PostgreSQL в корпорации ATRA. 
Проанализируй медленный запрос и предложи конкретную оптимизацию (индекс, переписывание запроса и т.д.).

ЗАПРОС:
{query_text}

СРЕДНЕЕ ВРЕМЯ: {avg_time:.2f} ms
КОЛИЧЕСТВО ВЫЗОВОВ: {query_data['calls']}
ПЛАН ВЫПОЛНЕНИЯ (EXPLAIN ANALYZE):
{explain_plan}

ОТВЕТЬ В ФОРМАТЕ:
1. ПРИЧИНА: почему запрос медленный.
2. ОПТИМИЗАЦИЯ: конкретный SQL для создания индекса или изменения запроса.
3. ОЖИДАЕМЫЙ ЭФФЕКТ: во сколько раз ускорится.

Если оптимизация требует создания индекса, используй формат:
CREATE INDEX CONCURRENTLY idx_name ON table_name (column_name);
"""
        try:
            analysis = await run_smart_agent_async(
                prompt, 
                expert_name="Игорь", 
                category="performance_audit"
            )
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing query via Victoria: {e}")
            return None

    async def log_optimization_hypothesis(self, query_data: Dict[str, Any], analysis: str):
        """Log the optimization hypothesis to knowledge_nodes and evolution_log."""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            try:
                # 1. Save to knowledge_nodes
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
                
                # 2. Add to evolution_log if table exists
                try:
                    await conn.execute("""
                        INSERT INTO evolution_log (event_type, description, metadata)
                        VALUES ('performance_audit', $1, $2)
                    """, f"Found slow query ({query_data['avg_exec_time_ms']:.1f}ms). Hypothesis generated.", meta)
                except:
                    pass # Table might not exist yet
                    
                logger.info("✅ Optimization hypothesis logged.")
            except Exception as e:
                logger.error(f"Error logging hypothesis: {e}")

    async def run_once(self):
        """Run one collection and analysis cycle."""
        logger.info("--- Watchdog Cycle Start ---")
        slow_queries = await self.collect_slow_queries()
        
        if not slow_queries:
            logger.info("No slow queries detected.")
            return

        logger.info(f"Found {len(slow_queries)} slow queries.")
        
        for q in slow_queries:
            analysis = await self.analyze_query(q)
            if analysis:
                await self.log_optimization_hypothesis(q, analysis)
                # In Task 4 we will add autonomous execution
        
        logger.info("--- Watchdog Cycle End ---")

    async def start(self):
        logger.info(f"Performance Watchdog started. Interval: {self.interval}s")
        while True:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"Error in watchdog loop: {e}")
            await asyncio.sleep(self.interval)

if __name__ == "__main__":
    watchdog = PerformanceWatchdog()
    asyncio.run(watchdog.start())
