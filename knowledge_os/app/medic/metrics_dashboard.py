"""
Metrics Dashboard — реальное время видимости действий Victoria.

Предоставляет:
1. Текущий статус всех компонентов
2. Статистику ошибок и исправлений
3. Историю действий
4. Прогноз проблем
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os",
)


class MetricsDashboard:
    """
    Панель метрик для мониторинга Victoria.

    Предоставляет:
    - real-time статус
    - статистику по ошибкам
    - историю действий
    - прогноз проблем
    """

    def __init__(self):
        self.conn: Optional[asyncpg.Connection] = None
        self._initialized = False
        self._start_time = time.time()
        self._actions_log: List[Dict] = []

    async def initialize(self):
        """Инициализация."""
        if self._initialized:
            return

        try:
            self.conn = await asyncpg.connect(DB_URL)

            # Таблица метрик
            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS victoria_metrics (
                    id SERIAL PRIMARY KEY,
                    metric_type VARCHAR(64) NOT NULL,
                    metric_name VARCHAR(128) NOT NULL,
                    metric_value FLOAT,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Таблица действий
            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS victoria_actions (
                    id SERIAL PRIMARY KEY,
                    action_type VARCHAR(64) NOT NULL,
                    action_description TEXT NOT NULL,
                    status VARCHAR(32) DEFAULT 'pending',
                    duration_seconds FLOAT,
                    error_message TEXT,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    completed_at TIMESTAMP
                )
            """)

            # Индексы
            await self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_type
                ON victoria_metrics(metric_type, created_at)
            """)
            await self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_actions_type
                ON victoria_actions(action_type, created_at)
            """)

            self._initialized = True
            logger.info("✅ [METRICS] Dashboard инициализирован")

        except Exception as e:
            logger.error(f"❌ [METRICS] Ошибка инициализации: {e}")

    async def log_action(
        self,
        action_type: str,
        description: str,
        status: str = "running",
        metadata: Optional[Dict] = None,
    ) -> int:
        """Записать действие."""
        if not self._initialized:
            await self.initialize()
        if not self.conn:
            return 0

        try:
            result = await self.conn.fetchrow(
                """
                INSERT INTO victoria_actions (action_type, action_description, status, metadata)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                action_type,
                description,
                status,
                json.dumps(metadata) if metadata else None,
            )
            action_id = result["id"]

            self._actions_log.append({
                "id": action_id,
                "type": action_type,
                "description": description,
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Keep only last 1000 actions in memory
            if len(self._actions_log) > 1000:
                self._actions_log = self._actions_log[-1000:]

            return action_id

        except Exception as e:
            logger.error(f"❌ [METRICS] Ошибка записи действия: {e}")
            return 0

    async def complete_action(
        self,
        action_id: int,
        status: str = "completed",
        error_message: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ):
        """Завершить действие."""
        if not self._initialized or not self.conn:
            return

        try:
            await self.conn.execute(
                """
                UPDATE victoria_actions
                SET status = $1, error_message = $2, duration_seconds = $3, completed_at = NOW()
                WHERE id = $4
                """,
                status,
                error_message,
                duration_seconds,
                action_id,
            )

        except Exception as e:
            logger.error(f"❌ [METRICS] Ошибка завершения действия: {e}")

    async def record_metric(
        self,
        metric_type: str,
        metric_name: str,
        value: float,
        metadata: Optional[Dict] = None,
    ):
        """Записать метрику."""
        if not self._initialized or not self.conn:
            return

        try:
            await self.conn.execute(
                """
                INSERT INTO victoria_metrics (metric_type, metric_name, metric_value, metadata)
                VALUES ($1, $2, $3, $4)
                """,
                metric_type,
                metric_name,
                value,
                json.dumps(metadata) if metadata else None,
            )

        except Exception as e:
            logger.error(f"❌ [METRICS] Ошибка записи метрики: {e}")

    async def get_realtime_status(self) -> Dict:
        """Получить текущий статус системы."""
        uptime = time.time() - self._start_time

        status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": round(uptime, 1),
            "uptime_human": self._format_uptime(uptime),
            "components": {},
            "recent_actions": self._actions_log[-10:],
        }

        # Проверяем компоненты
        components = {
            "victoria": "http://victoria-agent:8000/health",
            "veronica": "http://veronica-agent:8000/health",
            "mlx": "http://host.docker.internal:11435/health",
            "worker": "http://knowledge_os_worker:8000/metrics",
        }

        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                for name, url in components.items():
                    try:
                        resp = await client.get(url)
                        status["components"][name] = {
                            "status": "healthy" if resp.status_code == 200 else "unhealthy",
                            "status_code": resp.status_code,
                        }
                    except:
                        status["components"][name] = {
                            "status": "unreachable",
                            "status_code": 0,
                        }
        except:
            pass

        return status

    async def get_error_stats(self, hours: int = 24) -> Dict:
        """Получить статистику ошибок за период."""
        if not self._initialized or not self.conn:
            return {}

        try:
            # Ошибки из feedback_log
            errors = await self.conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN was_successful = TRUE THEN 1 END) as fixed,
                    COUNT(CASE WHEN was_successful = FALSE THEN 1 END) as failed,
                    COUNT(CASE WHEN was_successful IS NULL THEN 1 END) as pending
                FROM feedback_log
                WHERE created_at > NOW() - ($1 || ' hours')::INTERVAL
                """,
                str(hours),
            )

            # Паттерны
            patterns = await self.conn.fetchrow(
                """
                SELECT COUNT(*) as total,
                       SUM(count) as occurrences
                FROM error_patterns
                WHERE last_seen > NOW() - ($1 || ' hours')::INTERVAL
                """,
                str(hours),
            )

            return {
                "period_hours": hours,
                "errors": dict(errors) if errors else {},
                "patterns": dict(patterns) if patterns else {},
            }

        except Exception as e:
            logger.error(f"❌ [METRICS] Ошибка получения stats: {e}")
            return {}

    async def get_recent_actions(self, limit: int = 20) -> List[Dict]:
        """Получить последние действия."""
        if not self._initialized or not self.conn:
            return []

        try:
            actions = await self.conn.fetch(
                """
                SELECT * FROM victoria_actions
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
            return [dict(a) for a in actions]

        except Exception as e:
            logger.error(f"❌ [METRICS] Ошибка получения действий: {e}")
            return []

    async def get_predictions(self) -> Dict:
        """Прогноз проблем на основе метрик."""
        if not self._initialized or not self.conn:
            return {}

        predictions = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "predictions": [],
        }

        try:
            # Проверяем рост ошибок
            recent_errors = await self.conn.fetchval(
                """
                SELECT COUNT(*) FROM feedback_log
                WHERE created_at > NOW() - INTERVAL '1 hour'
                """
            )
            previous_errors = await self.conn.fetchval(
                """
                SELECT COUNT(*) FROM feedback_log
                WHERE created_at > NOW() - INTERVAL '2 hours'
                AND created_at < NOW() - INTERVAL '1 hour'
                """
            )

            if previous_errors > 0 and recent_errors > previous_errors * 1.5:
                predictions["predictions"].append({
                    "type": "error_rate_increase",
                    "severity": "warning",
                    "message": f"Rate of errors increased: {recent_errors} vs {previous_errors} (previous hour)",
                })

            # Проверяем повторяющиеся паттерны
            frequent_patterns = await self.conn.fetch(
                """
                SELECT container, error_type, count
                FROM error_patterns
                WHERE count > 10
                ORDER BY count DESC
                LIMIT 5
                """
            )
            for p in frequent_patterns:
                predictions["predictions"].append({
                    "type": "recurring_pattern",
                    "severity": "info",
                    "message": f"Recurring pattern in {p['container']}: {p['error_type']} (x{p['count']})",
                })

        except Exception as e:
            logger.error(f"❌ [METRICS] Ошибка прогнозов: {e}")

        return predictions

    def _format_uptime(self, seconds: float) -> str:
        """Форматировать uptime."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"


# Singleton
_dashboard: Optional[MetricsDashboard] = None


def get_dashboard() -> MetricsDashboard:
    """Получить singleton MetricsDashboard."""
    global _dashboard
    if _dashboard is None:
        _dashboard = MetricsDashboard()
    return _dashboard
