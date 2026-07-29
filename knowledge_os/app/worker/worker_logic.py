import json
import logging
import os
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _structured_cancel_reason(reason_code: str, component: str, details: str = "") -> dict:
    """Структурированная причина системного сброса/отмены задачи."""
    payload = {
        "reason_code": reason_code,
        "component": component,
        "policy": "auto_requeue_delegation_v1",
        "at": datetime.utcnow().isoformat() + "Z",
    }
    if details:
        payload["details"] = details[:500]
    return payload


async def _emit_delegation_metrics(conn, alert_threshold: int) -> None:
    """Печатает метрики и алерт по stuck delegation задачам.

    v130: cancelled — исторический ledger политики timeout-cap / triage, не stuck.
    stuck = failed + in_progress older than SLA (default 30m).
    """
    try:
        stale_minutes = max(5, int(os.getenv("DELEGATION_STUCK_IN_PROGRESS_MINUTES", "30")))
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending') AS pending_cnt,
                COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress_cnt,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed_cnt,
                COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_cnt,
                COUNT(*) FILTER (
                    WHERE status = 'in_progress'
                      AND COALESCE(updated_at, created_at)
                          < NOW() - make_interval(mins => $1::int)
                ) AS stale_in_progress_cnt
            FROM tasks
            WHERE metadata->>'source' = 'victoria_monster_delegation'
            """,
            stale_minutes,
        )
        if not row:
            return
        pending_cnt = int(row["pending_cnt"] or 0)
        in_progress_cnt = int(row["in_progress_cnt"] or 0)
        failed_cnt = int(row["failed_cnt"] or 0)
        cancelled_cnt = int(row["cancelled_cnt"] or 0)
        stale_ip_cnt = int(row["stale_in_progress_cnt"] or 0)
        print(
            f"[{datetime.now()}] 📊 [DELEGATION_METRICS] pending={pending_cnt} "
            f"in_progress={in_progress_cnt} stale_in_progress={stale_ip_cnt} "
            f"failed={failed_cnt} cancelled={cancelled_cnt}"
        )
        # Cancelled is ledger noise after work_item_timeout_exhausted / triage — not stuck.
        stuck_total = failed_cnt + stale_ip_cnt
        if stuck_total >= alert_threshold:
            print(
                f"[{datetime.now()}] 🚨 [DELEGATION_ALERT] stuck_delegation={stuck_total} "
                f"(failed={failed_cnt}, stale_in_progress={stale_ip_cnt}, "
                f"cancelled_ledger={cancelled_cnt}) threshold={alert_threshold}"
            )
    except Exception as _metrics_err:
        logger.debug("Delegation metrics failed: %s", _metrics_err)


async def _auto_requeue_delegation(conn, max_rows: int, max_requeues_per_task: int) -> int:
    """Policy-driven восстановление delegation задач без активных дублей."""
    try:
        result = await conn.execute(
            """
            WITH candidate AS (
                SELECT t.id, t.title, COALESCE(t.project_context, 'default') AS pc
                FROM tasks t
                WHERE t.status IN ('cancelled', 'failed')
                  AND t.metadata->>'source' = 'victoria_monster_delegation'
                  AND COALESCE((t.metadata->>'failed_requires_intervention')::boolean, false) = false
                  AND COALESCE(t.metadata->>'diagnostic_path', '') NOT IN (
                      'delegation_manual_triage',
                      'progress_guard_manual_triage',
                      'expert_worker_manual_triage'
                  )
                  AND COALESCE(t.metadata->>'auto_fallback_reason', '') NOT LIKE '%manual_triage%'
                  AND COALESCE(t.metadata->>'auto_fallback_reason', '') NOT LIKE '%exhausted%'
                  AND (
                      CASE
                          WHEN COALESCE(t.metadata->>'auto_requeue_count', '') ~ '^[0-9]+$'
                          THEN (t.metadata->>'auto_requeue_count')::int
                          ELSE 0
                      END
                  ) < $2::int
                  AND NOT EXISTS (
                      SELECT 1
                      FROM tasks t2
                      WHERE t2.status IN ('pending', 'in_progress')
                        AND t2.title = t.title
                        AND COALESCE(t2.project_context, 'default') = COALESCE(t.project_context, 'default')
                  )
                ORDER BY t.updated_at ASC
                LIMIT $1::int
            )
            UPDATE tasks t
            SET status = 'pending',
                updated_at = NOW(),
                metadata = COALESCE(t.metadata, '{}'::jsonb)
                    || jsonb_build_object(
                        'restored_from', t.status,
                        'restored_by', 'auto_requeue_delegation_policy',
                        'auto_requeue_count',
                        (
                            CASE
                                WHEN COALESCE(t.metadata->>'auto_requeue_count', '') ~ '^[0-9]+$'
                                THEN (t.metadata->>'auto_requeue_count')::int
                                ELSE 0
                            END
                        ) + 1,
                        'cancel_reason', $3::jsonb
                    )
            FROM candidate c
            WHERE t.id = c.id
            """,
            max_rows,
            max_requeues_per_task,
            json.dumps(
                _structured_cancel_reason(
                    "delegation_auto_requeued",
                    "smart_worker_autonomous",
                    "restored from failed/cancelled by policy",
                )
            ),
        )
        if result and result.startswith("UPDATE"):
            return int(result.split()[-1])
    except Exception as _requeue_err:
        logger.debug("Auto requeue delegation failed: %s", _requeue_err)
    return 0
