"""
Data Retention — консервативная очистка только кэшевых/метрик-таблиц.
НЕ трогает: knowledge_nodes, experts, domains, tasks, interaction_logs.
См. docs/DATA_RETENTION_ANALYSIS.md
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CleanupResult:
    """Результат очистки одной таблицы."""
    table: str
    deleted: int
    dry_run: bool
    error: Optional[str] = None


@dataclass
class RetentionReport:
    """Отчёт об очистке."""
    timestamp: str
    dry_run: bool
    results: List[CleanupResult] = field(default_factory=list)
    total_deleted: int = 0


class DataRetentionManager:
    """
    Консервативный менеджер очистки. Очищает только:
    - real_time_metrics (записи старше retention_days)
    - semantic_ai_cache (last_used_at старше retention_days)
    """

    # Таблицы, которые НИКОГДА не трогаем
    FORBIDDEN_TABLES = frozenset({
        "knowledge_nodes", "experts", "domains", "tasks",
        "interaction_logs", "feedback", "quality_issues",
    })

    def __init__(
        self,
        pool: Any,
        retention_days: int = 90,
        batch_size: int = 500,
    ):
        self.pool = pool
        self.retention_days = retention_days
        self.batch_size = batch_size
        self._last_report: Optional[RetentionReport] = None

    async def run_cleanup(
        self,
        dry_run: bool = True,
        tables: Optional[List[str]] = None,
    ) -> RetentionReport:
        """
        Запуск очистки.
        dry_run=True — только подсчёт, без удаления (рекомендуется по умолчанию).
        tables — список таблиц (None = только разрешённые).
        """
        allowed = {"real_time_metrics", "semantic_ai_cache"}
        if tables:
            for t in tables:
                if t in self.FORBIDDEN_TABLES:
                    logger.warning("Пропуск запрещённой таблицы: %s", t)
                    continue
                allowed.add(t)
        else:
            tables = list(allowed)

        report = RetentionReport(
            timestamp=datetime.now().isoformat(),
            dry_run=dry_run,
        )
        total = 0

        async with self.pool.acquire() as conn:
            for table in tables:
                if table not in allowed:
                    continue
                try:
                    deleted = await self._clean_table(conn, table, dry_run)
                    report.results.append(CleanupResult(table=table, deleted=deleted, dry_run=dry_run))
                    total += deleted
                except Exception as e:
                    logger.exception("Ошибка очистки %s: %s", table, e)
                    report.results.append(
                        CleanupResult(table=table, deleted=0, dry_run=dry_run, error=str(e))
                    )

        report.total_deleted = total
        self._last_report = report

        if dry_run:
            logger.info("DataRetention DRY-RUN: удалено бы %s записей", total)
        else:
            logger.info("DataRetention: удалено %s записей", total)

        return report

    async def _clean_table(self, conn, table: str, dry_run: bool) -> int:
        """Очистка одной таблицы пачками."""
        if table == "real_time_metrics":
            cutoff = f"created_at < NOW() - INTERVAL '{self.retention_days} days'"
            id_col = "id"
        elif table == "semantic_ai_cache":
            # last_used_at или created_at, если last_used_at NULL
            cutoff = f"COALESCE(last_used_at, created_at) < NOW() - INTERVAL '{self.retention_days} days'"
            id_col = "id"
        else:
            return 0

        # Проверяем существование таблицы
        exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=$1)",
            table,
        )
        if not exists:
            logger.debug("Таблица %s не найдена, пропуск", table)
            return 0

        if dry_run:
            if table == "real_time_metrics":
                total_deleted = await conn.fetchval(
                    f"SELECT COUNT(*) FROM real_time_metrics WHERE {cutoff}"
                )
            else:
                total_deleted = await conn.fetchval(
                    f"SELECT COUNT(*) FROM semantic_ai_cache WHERE {cutoff}"
                )
            return total_deleted or 0

        total_deleted = 0
        while True:
            if table == "real_time_metrics":
                sub = f"SELECT id FROM real_time_metrics WHERE {cutoff} ORDER BY id LIMIT {self.batch_size}"
            else:
                sub = f"SELECT id FROM semantic_ai_cache WHERE {cutoff} LIMIT {self.batch_size}"

            deleted = await conn.execute(
                f"DELETE FROM {table} WHERE {id_col} IN ({sub})"
            )
            n = int(deleted.split()[-1]) if deleted else 0
            total_deleted += n
            if n < self.batch_size:
                break
            await asyncio.sleep(0.05)

        return total_deleted

    def get_last_report(self) -> Optional[RetentionReport]:
        return self._last_report
