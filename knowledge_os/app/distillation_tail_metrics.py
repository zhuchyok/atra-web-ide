"""
Shared distillation tail metric helpers.

Single source of truth for "eligible_now" selection logic.
"""

from __future__ import annotations

import asyncpg

DISTILL_ELIGIBLE_WHERE_SQL = """
is_verified = TRUE
AND
content IS NOT NULL
AND (metadata->>'distilled' IS NULL OR metadata->>'distilled' = 'false')
AND COALESCE(metadata->>'distill_status', 'pending') != 'failed'
AND COALESCE(metadata->>'distill_status', 'pending') != 'in_progress'
AND (
  metadata->>'distill_status' IS DISTINCT FROM 'retry'
  OR COALESCE((metadata->>'distill_next_retry_ts')::bigint, 0)
     <= EXTRACT(EPOCH FROM NOW())::bigint
)
""".strip()


DISTILL_ELIGIBLE_COUNT_SQL = f"""
SELECT COUNT(*)
FROM knowledge_nodes
WHERE {DISTILL_ELIGIBLE_WHERE_SQL}
""".strip()


DISTILL_CAMPAIGN_PROGRESS_SQL = f"""
SELECT
  COUNT(*) FILTER (
    WHERE COALESCE(metadata->>'distill_owner','')='cursor_campaign'
      AND COALESCE(metadata->>'distill_status','')='done'
  ),
  COUNT(*) FILTER (
    WHERE COALESCE(metadata->>'distill_owner','')='cursor_campaign'
      AND COALESCE(metadata->>'distill_status','')='in_progress'
  ),
  COUNT(*) FILTER (
    WHERE COALESCE(metadata->>'distill_owner','')='cursor_campaign'
      AND COALESCE(metadata->>'distill_status','')='retry'
  ),
  COUNT(*) FILTER (WHERE {DISTILL_ELIGIBLE_WHERE_SQL})
FROM knowledge_nodes
""".strip()


async def get_distill_eligible_now(conn: asyncpg.Connection) -> int:
    return int(await conn.fetchval(DISTILL_ELIGIBLE_COUNT_SQL) or 0)
