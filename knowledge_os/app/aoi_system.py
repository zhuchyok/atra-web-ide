"""
Autonomous Task Orchestration (AOI) - Автономная оркестрация задач
Реализация радикального решения из Директивы Совета Директоров от 2026-02-14.

Функционал:
1. Балансировка нагрузки между командами в реальном времени.
2. Автоматическая корректировка приоритетов на основе KPI.
3. Синхронизация данных между подсистемами.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Database connection
try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


@dataclass
class AOIStats:
    total_tasks: int
    active_tasks: int
    load_balance_score: float
    priority_shifts: int
    efficiency_gain: float


class AutonomousOrchestrator:
    """
    AOI - Система автономного управления задачами.
    Работает как фоновый демон, оптимизирующий очередь задач.
    """

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.is_running = False
        self._last_cycle_time = 0
        self._stats = AOIStats(0, 0, 1.0, 0, 0.0)

    async def start(self):
        """Запустить цикл AOI"""
        if self.is_running:
            return
        self.is_running = True
        logger.info("🚀 AOI: Автономная оркестрация запущена")

        while self.is_running:
            try:
                await self._run_optimization_cycle()
                # Цикл каждые 5 минут для оперативного реагирования
                await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"❌ AOI Cycle Error: {e}")
                await asyncio.sleep(60)

    async def _run_optimization_cycle(self):
        """Один цикл оптимизации задач"""
        t0 = time.time()
        conn = await asyncpg.connect(self.db_url)
        try:
            # 1. Балансировка нагрузки (Load Balancing)
            await self._balance_expert_workload(conn)

            # 2. Корректировка приоритетов (Priority Re-balancing)
            await self._adjust_task_priorities(conn)

            # 3. Синхронизация зависимостей (Dependency Sync)
            await self._sync_task_dependencies(conn)

            # 4. Сохранение инсайта в Knowledge OS (Singularity 10.0)
            await self._record_aoi_insight(conn)

            self._last_cycle_time = time.time() - t0
            logger.info(f"✅ AOI Cycle complete in {self._last_cycle_time:.2f}s")

        finally:
            await conn.close()

    async def _record_aoi_insight(self, conn):
        """Записать отчет о работе AOI в базу знаний"""
        try:
            domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = 'System' LIMIT 1")
            content = f"AOI Optimization Cycle: Load balanced, priorities adjusted. Last cycle duration: {self._last_cycle_time:.2f}s"
            meta = json.dumps(
                {"type": "aoi_optimization", "timestamp": datetime.now(timezone.utc).isoformat()}
            )

            await conn.execute(
                """
                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                VALUES ($1, $2, 1.0, $3, true)
            """,
                domain_id,
                content,
                meta,
            )
        except Exception as e:
            logger.debug(f"AOI insight failed: {e}")

    async def _balance_expert_workload(self, conn):
        """Перераспределение задач между перегруженными и свободными экспертами"""
        # Находим перегруженных экспертов (>5 активных задач)
        overloaded = await conn.fetch("""
            SELECT assignee_expert_id, COUNT(*) as task_count
            FROM tasks
            WHERE status IN ('pending', 'in_progress')
            AND assignee_expert_id IS NOT NULL
            GROUP BY assignee_expert_id
            HAVING COUNT(*) > 5
        """)

        for row in overloaded:
            expert_id = row["assignee_expert_id"]
            # Ищем свободного эксперта в том же домене
            # (Логика из enhanced_orchestrator, но более агрессивная)
            task_to_move = await conn.fetchrow(
                """
                SELECT id, domain_id FROM tasks
                WHERE assignee_expert_id = $1 AND status = 'pending'
                ORDER BY created_at ASC LIMIT 1
            """,
                expert_id,
            )

            if task_to_move:
                new_expert = await conn.fetchval(
                    """
                    SELECT e.id FROM experts e
                    LEFT JOIN tasks t ON t.assignee_expert_id = e.id
                        AND t.status IN ('pending', 'in_progress')
                    WHERE e.id != $1
                    GROUP BY e.id
                    ORDER BY COUNT(t.id) ASC
                    LIMIT 1
                """,
                    expert_id,
                )

                if new_expert:
                    await conn.execute(
                        """
                        UPDATE tasks SET assignee_expert_id = $1,
                        metadata = metadata || '{"aoi_reassigned": true}'::jsonb
                        WHERE id = $2
                    """,
                        new_expert,
                        task_to_move["id"],
                    )
                    logger.info(
                        f"⚖️ AOI: Task {task_to_move['id']} moved to expert {new_expert} for balancing"
                    )

    async def _adjust_task_priorities(self, conn):
        """Повышение приоритета застоявшихся задач"""
        # Задачи, которые висят больше 24 часов в pending
        stale_tasks = await conn.execute("""
            UPDATE tasks
            SET priority = 'high',
                metadata = metadata || '{"aoi_priority_boost": "stale"}'::jsonb
            WHERE status = 'pending'
            AND created_at < NOW() - INTERVAL '24 hours'
            AND priority != 'high' AND priority != 'urgent'
        """)
        if "UPDATE 0" not in str(stale_tasks):
            logger.info("⚡ AOI: Boosted priority for stale tasks")

    async def _sync_task_dependencies(self, conn):
        """Автоматическое помечание задач как ready_for_execution"""
        # Если у задачи есть parent_task_id, проверяем статус родителя
        # (Упрощенная версия для первой итерации)
        await conn.execute("""
            UPDATE tasks
            SET metadata = metadata || '{"ready_for_execution": true}'::jsonb
            WHERE status = 'pending'
            AND (metadata->>'ready_for_execution') IS NULL
        """)

    async def get_stats(self) -> AOIStats:
        """Получить текущую статистику AOI"""
        return self._stats


async def main():
    aoi = AutonomousOrchestrator()
    await aoi.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
