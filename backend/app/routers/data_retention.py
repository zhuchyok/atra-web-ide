"""
API Data Retention — ручной запуск очистки (DRY-RUN по умолчанию).
"""
from fastapi import APIRouter, Request
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/api/data-retention", tags=["data-retention"])


@router.post("/cleanup")
async def run_cleanup(
    request: Request,
    dry_run: bool = True,
    tables: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Запуск очистки устаревших записей.
    - dry_run=True (по умолчанию): только подсчёт, без удаления.
    - tables: через запятую, например real_time_metrics,semantic_ai_cache.
    """
    pool = getattr(request.app.state, "knowledge_os_pool", None)
    if not pool:
        return {"error": "Database pool not available", "status": "unavailable"}

    from app.services.data_retention import DataRetentionManager
    from app.config import get_settings
    settings = get_settings()
    retention = int(getattr(settings, "data_retention_days", 90))

    manager = DataRetentionManager(pool, retention_days=retention)
    tbl_list = [t.strip() for t in tables.split(",")] if tables else None

    report = await manager.run_cleanup(dry_run=dry_run, tables=tbl_list)

    return {
        "status": "dry_run" if dry_run else "completed",
        "timestamp": report.timestamp,
        "total_deleted": report.total_deleted,
        "results": [
            {
                "table": r.table,
                "deleted": r.deleted,
                "error": r.error,
            }
            for r in report.results
        ],
    }


@router.get("/report")
async def get_last_report(request: Request) -> Dict[str, Any]:
    """Последний отчёт об очистке (если был)."""
    # Report хранится в экземпляре, который создаётся при каждом cleanup.
    # Для простоты возвращаем инструкцию.
    return {
        "message": "Запустите POST /api/data-retention/cleanup для отчёта",
        "safe_tables": ["real_time_metrics", "semantic_ai_cache"],
        "forbidden": ["knowledge_nodes", "experts", "domains", "tasks", "interaction_logs"],
    }
