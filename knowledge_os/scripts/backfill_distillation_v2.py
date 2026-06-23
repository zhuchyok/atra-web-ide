#!/usr/bin/env python3
"""
Backfill distillation v2 metadata for already-distilled knowledge nodes.

Safe-by-default behavior:
- small update batches
- bounded statement timeout
- optional pause between batches
"""

from __future__ import annotations

import argparse
import asyncio
import os

import asyncpg

DEFAULT_DB_URL = os.getenv(
    "POSTGRES_DIRECT_URL",
    os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os"),
)


BACKFILL_SQL = """
WITH pick AS (
  SELECT id
  FROM knowledge_nodes
  WHERE metadata->>'distilled'='true'
    AND COALESCE(metadata->>'distillation_schema_version','') <> 'v2'
  LIMIT $1
),
patch_rows AS (
  SELECT kn.id,
         jsonb_build_object(
           'distillation_schema_version','v2',
           'decision_context', COALESCE(kn.metadata->>'decision_context', kn.metadata->>'category', kn.metadata->>'type', 'strategy'),
           'risk_level', COALESCE(kn.metadata->>'risk_level','medium'),
           'counter_claims', COALESCE(kn.metadata->'counter_claims','[]'::jsonb),
           'invalidates_if', COALESCE(kn.metadata->'invalidates_if','[]'::jsonb),
           'actionability_score', COALESCE((kn.metadata->>'actionability_score')::numeric, 0.8),
           'source_reliability_score', COALESCE((kn.metadata->>'source_reliability_score')::numeric, 0.7),
           'applicability_scope', COALESCE(kn.metadata->>'applicability_scope', kn.metadata->>'category', 'strategy'),
           'evidence_strength', COALESCE(kn.metadata->>'evidence_strength','moderate'),
           'freshness_half_life_days', COALESCE((kn.metadata->>'freshness_half_life_days')::int, 180),
           'core_thesis', COALESCE(kn.metadata->>'core_thesis', kn.metadata->>'wisdom_summary', kn.metadata->>'summary', ''),
           'mental_models', COALESCE(kn.metadata->'mental_models','[]'::jsonb),
           'claims', COALESCE(kn.metadata->'claims','[]'::jsonb),
           'takeaways', COALESCE(kn.metadata->'takeaways', to_jsonb(ARRAY[COALESCE(kn.metadata->>'instruction','')]))
         ) AS patch
  FROM knowledge_nodes kn
  JOIN pick p ON p.id = kn.id
),
updated AS (
  UPDATE knowledge_nodes kn
  SET metadata = COALESCE(kn.metadata,'{}'::jsonb) || pr.patch
  FROM patch_rows pr
  WHERE kn.id = pr.id
  RETURNING 1
)
SELECT count(*)::int FROM updated
"""


async def run() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=DEFAULT_DB_URL)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-batches", type=int, default=500)
    parser.add_argument("--sleep-ms", type=int, default=150)
    parser.add_argument("--statement-timeout-ms", type=int, default=20000)
    args = parser.parse_args()

    conn = await asyncpg.connect(args.database_url)
    total = 0
    try:
        await conn.execute(f"SET statement_timeout = '{max(1000, args.statement_timeout_ms)}ms'")
        for i in range(1, args.max_batches + 1):
            updated = int(await conn.fetchval(BACKFILL_SQL, max(1, args.batch_size)) or 0)
            total += updated
            print(f"batch={i} updated={updated} total={total}")
            if updated < args.batch_size:
                break
            if args.sleep_ms > 0:
                await asyncio.sleep(args.sleep_ms / 1000.0)
    finally:
        await conn.close()

    print(f"done total_updated={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
