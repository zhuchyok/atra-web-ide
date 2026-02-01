"""
Показатели Mac Studio / хоста: CPU, память, диск.
GET /api/system-metrics — JSON для дашборда и мониторинга.
Содержит также count_experts, count_knowledge_nodes для алертов (рекомендации экспертов 2026-02-01).
"""
import logging
import os
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["System metrics"])


@router.get("/system-metrics")
async def system_metrics():
    """
    Текущие показатели системы (CPU, память, диск).
    Если бэкенд в Docker — метрики контейнера; на хосте — метрики Mac Studio.
    """
    try:
        import psutil
    except ImportError:
        return {
            "success": False,
            "error": "psutil не установлен",
            "cpu": None,
            "ram": None,
            "disk": None,
        }

    try:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        cpu_count = psutil.cpu_count() or 0
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        result = {
            "success": True,
            "cpu": {
                "percent": round(cpu_percent, 1),
                "count": cpu_count,
            },
            "ram": {
                "percent": round(ram.percent, 1),
                "used_gb": round(ram.used / (1024**3), 2),
                "total_gb": round(ram.total / (1024**3), 2),
                "available_gb": round(ram.available / (1024**3), 2),
            },
            "disk": {
                "percent": round((disk.used / disk.total) * 100, 1),
                "used_gb": round(disk.used / (1024**3), 2),
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
            },
        }
        # DB metrics для алертов (volume switch detection)
        try:
            import asyncpg
            db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
            conn = await asyncpg.connect(db_url)
            try:
                experts = await conn.fetchval("SELECT COUNT(*) FROM experts")
                nodes = await conn.fetchval("SELECT COUNT(*) FROM knowledge_nodes")
                result["db"] = {"experts": experts, "knowledge_nodes": nodes}
                # Пороги для алертов (см. docs/INCIDENT_DB_VOLUME_SWITCH)
                result["db"]["healthy"] = (experts or 0) >= 80 and (nodes or 0) >= 10000
                # Task execution metrics (Этап 6 плана Resilient Task Execution)
                try:
                    base_24h = "status = 'completed' AND updated_at > NOW() - INTERVAL '24 hours'"
                    tasks_ai = await conn.fetchval(
                        f"SELECT COUNT(*) FROM tasks WHERE {base_24h} "
                        "AND (metadata->>'execution_mode' IS NULL OR metadata->>'execution_mode' != 'rule_based')"
                    )
                    tasks_rule = await conn.fetchval(
                        f"SELECT COUNT(*) FROM tasks WHERE {base_24h} "
                        "AND metadata->>'execution_mode' = 'rule_based'"
                    )
                    tasks_deferred = await conn.fetchval(
                        f"SELECT COUNT(*) FROM tasks WHERE {base_24h} "
                        "AND metadata->>'deferred_to_human' = 'true'"
                    )
                    tasks_failed = await conn.fetchval(
                        "SELECT COUNT(*) FROM tasks WHERE status = 'failed' AND updated_at > NOW() - INTERVAL '24 hours'"
                    )
                    result["tasks_24h"] = {
                        "completed_by_ai": tasks_ai or 0,
                        "completed_by_rule": tasks_rule or 0,
                        "deferred_to_human": tasks_deferred or 0,
                        "failed": tasks_failed or 0,
                    }
                    total_done = (tasks_ai or 0) + (tasks_rule or 0)
                    total_all = total_done + (tasks_deferred or 0) + (tasks_failed or 0)
                    if total_all > 5:
                        deferred_ratio = (tasks_deferred or 0) / total_all
                        failed_ratio = (tasks_failed or 0) / total_all
                        if deferred_ratio > 0.3 or failed_ratio > 0.2:
                            alert_msg = (
                                f"High deferred/failed ratio: deferred={deferred_ratio:.0%}, failed={failed_ratio:.0%}"
                            )
                            result["tasks_24h"]["alert"] = alert_msg
                            logger.warning(
                                "Task execution alert: deferred_to_human=%.0f%%, failed=%.0f%%",
                                deferred_ratio * 100, failed_ratio * 100
                            )
                            try:
                                from app.services.telegram_alerts import send_task_execution_alert
                                await send_task_execution_alert(
                                    deferred_ratio, failed_ratio, alert_msg
                                )
                            except Exception as te:
                                logger.debug("Telegram alert: %s", te)
                except Exception as te:
                    logger.debug("Task metrics: %s", te)
            finally:
                await conn.close()
        except Exception as e:
            logger.debug("DB metrics: %s", e)
            result["db"] = {"error": str(e), "healthy": False}
        return result
    except Exception as e:
        logger.error("system_metrics: %s", e, exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "cpu": None,
            "ram": None,
            "disk": None,
        }
