"""
OKR service — Grove/Doerr lite for ATRA.

Active period only (default 2026-H2). Board / morning / dashboard should
call these helpers so stale Q4-2025 goals stop dominating context.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Sequence

import asyncpg

logger = logging.getLogger(__name__)

ACTIVE_OKR_PERIOD = os.getenv("ACTIVE_OKR_PERIOD", "2026-H2").strip() or "2026-H2"


def get_active_okr_period() -> str:
    return ACTIVE_OKR_PERIOD


async def fetch_active_okrs(
    conn: asyncpg.Connection,
    *,
    with_key_results: bool = False,
    limit: Optional[int] = None,
) -> List[asyncpg.Record]:
    """Return OKR rows for the active period only."""
    period = get_active_okr_period()
    if with_key_results:
        sql = """
            SELECT o.id, o.objective, o.department, o.period, o.created_at,
                   kr.id AS kr_id, kr.description AS kr_description,
                   kr.current_value, kr.target_value, kr.unit, kr.last_updated_at
            FROM okrs o
            LEFT JOIN key_results kr ON kr.okr_id = o.id
            WHERE o.period = $1
            ORDER BY o.created_at ASC, kr.description ASC
        """
        rows = await conn.fetch(sql, period)
        return list(rows)

    sql = """
        SELECT id, objective, department, period, created_at
        FROM okrs
        WHERE period = $1
        ORDER BY created_at ASC
    """
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    rows = await conn.fetch(sql, period)
    return list(rows)


def format_okr_context(okrs: Sequence[asyncpg.Record]) -> str:
    if not okrs:
        return ""
    lines = []
    for o in okrs:
        dept = o.get("department") or "—"
        lines.append(f"- {o['objective']} ({dept}, {o['period']})")
    return "\n".join(lines)


async def refresh_key_results_from_metrics(conn: asyncpg.Connection) -> int:
    """
    Push live metrics into key_results.current_value for active period.
    Matching is by description substring (stable seed strings).
    """
    period = get_active_okr_period()
    metrics = await conn.fetchrow(
        """
        SELECT
          (SELECT COUNT(*) FROM knowledge_nodes) AS nodes_total,
          (SELECT COUNT(*) FROM knowledge_nodes
             WHERE metadata->>'cycle' LIKE 'nightly_council%'
               AND created_at > NOW() - INTERVAL '7 days') AS council_7d,
          (SELECT COUNT(*) FROM knowledge_nodes
             WHERE metadata->>'type' = 'mentorship_note'
               AND created_at > NOW() - INTERVAL '7 days') AS mentor_7d,
          (SELECT COUNT(*) FROM tasks WHERE embedding IS NOT NULL) AS tasks_embedded,
          (SELECT COUNT(*) FROM tasks
             WHERE status = 'failed'
               AND updated_at > NOW() - INTERVAL '7 days') AS failed_7d,
          (SELECT COUNT(*) FROM tasks
             WHERE status IN ('pending', 'in_progress')
               AND updated_at < NOW() - INTERVAL '4 hours') AS stale_4h
        """
    )
    if not metrics:
        return 0

    mapping = [
        ("узлов знаний", float(metrics["nodes_total"])),
        ("дебат", float(metrics["council_7d"])),
        ("council", float(metrics["council_7d"])),
        ("ментор", float(metrics["mentor_7d"])),
        ("mentorship", float(metrics["mentor_7d"])),
        ("embedding", float(metrics["tasks_embedded"])),
        ("провален", float(metrics["failed_7d"])),
        ("failed", float(metrics["failed_7d"])),
        ("stale", float(metrics["stale_4h"])),
        ("зависш", float(metrics["stale_4h"])),
    ]

    krs = await conn.fetch(
        """
        SELECT kr.id, kr.description
        FROM key_results kr
        JOIN okrs o ON o.id = kr.okr_id
        WHERE o.period = $1
        """,
        period,
    )
    updated = 0
    for kr in krs:
        desc = (kr["description"] or "").lower()
        value = None
        for needle, val in mapping:
            if needle in desc:
                value = val
                break
        if value is None:
            continue
        await conn.execute(
            """
            UPDATE key_results
            SET current_value = $1, last_updated_at = NOW()
            WHERE id = $2
            """,
            value,
            kr["id"],
        )
        updated += 1
    return updated


async def ensure_active_okrs_seeded(conn: asyncpg.Connection) -> Dict[str, Any]:
    """
    Idempotent seed for ACTIVE_OKR_PERIOD (2026-H2 by default).
    Does not delete historical OKRs — Board simply ignores non-active periods.
    """
    period = get_active_okr_period()
    existing = await conn.fetchval(
        "SELECT COUNT(*) FROM okrs WHERE period = $1", period
    )
    if existing and int(existing) >= 3:
        refreshed = await refresh_key_results_from_metrics(conn)
        return {"seeded": False, "period": period, "count": int(existing), "refreshed_kr": refreshed}

    specs = [
        {
            "objective": (
                "Offline-First стабильность: корпорация устойчиво работает на Mac Studio "
                "(Victoria / MLX / Ollama / Postgres) без деградации в облако как норму"
            ),
            "department": "Atra Core",
            "krs": [
                (
                    "Проваленных задач за 7 дней (failed) — чем меньше, тем лучше",
                    5.0,
                    "шт",
                ),
                (
                    "Зависших pending/in_progress старше 4ч (stale)",
                    0.0,
                    "шт",
                ),
            ],
        },
        {
            "objective": (
                "Живая Wisdom Fabric: mentorship, SOP и Expert Council непрерывно "
                "пополняют корпоративную мудрость"
            ),
            "department": "Wisdom",
            "krs": [
                ("Дебаты Expert Council за 7 дней (nightly_council)", 4.0, "шт"),
                ("Советы ментора (mentorship_note) за 7 дней", 5.0, "шт"),
                ("Completed tasks с embedding (база Success Retrieval)", 500.0, "шт"),
            ],
        },
        {
            "objective": (
                "Интеллектуальный капитал с измеримым ROI: знания используются, "
                "а не только накапливаются"
            ),
            "department": "Knowledge",
            "krs": [
                ("Объем базы знаний (узлов знаний)", 120000.0, "ед"),
                (
                    "Completed tasks с embedding (coverage для retrieval)",
                    500.0,
                    "шт",
                ),
            ],
        },
    ]

    created = 0
    for spec in specs:
        okr_id = await conn.fetchval(
            """
            INSERT INTO okrs (objective, department, period, created_at)
            VALUES ($1, $2, $3, NOW())
            RETURNING id
            """,
            spec["objective"],
            spec["department"],
            period,
        )
        created += 1
        for desc, target, unit in spec["krs"]:
            await conn.execute(
                """
                INSERT INTO key_results
                    (okr_id, description, current_value, target_value, unit, last_updated_at)
                VALUES ($1, $2, 0, $3, $4, NOW())
                """,
                okr_id,
                desc,
                target,
                unit,
            )

    refreshed = await refresh_key_results_from_metrics(conn)
    logger.info(
        "Seeded %s OKRs for period=%s (refreshed_kr=%s)", period, period, refreshed
    )
    return {"seeded": True, "period": period, "count": created, "refreshed_kr": refreshed}


async def _main() -> None:
    db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DIRECT_URL")
    if not db_url:
        raise SystemExit("Set DATABASE_URL or POSTGRES_DIRECT_URL")
    conn = await asyncpg.connect(db_url)
    try:
        result = await ensure_active_okrs_seeded(conn)
        print(result)
        rows = await fetch_active_okrs(conn, with_key_results=True)
        for r in rows:
            print(
                f"- {r['objective'][:60]} | KR={r.get('kr_description')} "
                f"{r.get('current_value')}/{r.get('target_value')} {r.get('unit')}"
            )
    finally:
        await conn.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
