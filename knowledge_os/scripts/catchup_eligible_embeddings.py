#!/usr/bin/env python3
"""One-shot eligible embedding catch-up (model loads once). Target: >=80%."""

from __future__ import annotations

import asyncio
import os
import sys
import time

# Do NOT force HF offline — first load may need hub if cache incomplete.
for _k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
    if os.environ.get(_k) in ("1", "true", "True"):
        os.environ.pop(_k, None)


def _setup_path() -> None:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo not in sys.path:
        sys.path.insert(0, repo)
    app_dir = os.path.join(repo, "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)


async def main() -> int:
    _setup_path()
    import asyncpg
    from embedding_eligibility import ELIGIBLE_WHERE, backfill_eligible_embeddings

    db = os.environ.get(
        "DATABASE_URL",
        "postgresql://admin:secret@localhost:6432/knowledge_os",  # pragma: allowlist secret
    )
    target = float(os.getenv("EMBED_CATCHUP_TARGET", "0.80"))
    batch = max(100, min(int(os.getenv("EMBED_CATCHUP_BATCH", "2000")), 2000))
    max_rounds = max(1, int(os.getenv("EMBED_CATCHUP_MAX_ROUNDS", "20")))

    for round_n in range(1, max_rounds + 1):
        conn = await asyncpg.connect(db)
        try:
            have, total = await conn.fetchrow(
                f"""
                SELECT COUNT(*) FILTER (WHERE embedding IS NOT NULL), COUNT(*)
                FROM knowledge_nodes
                WHERE ({ELIGIBLE_WHERE})
                """
            )
        finally:
            await conn.close()

        pct = (have / total) if total else 0.0
        print(
            f"CATCHUP round={round_n} eligible={have}/{total} ({pct * 100:.2f}%)",
            flush=True,
        )
        if pct >= target:
            print("TARGET_REACHED", flush=True)
            return 0

        t0 = time.time()
        stats = await backfill_eligible_embeddings(limit=batch)
        print(f"batch={stats} elapsed={time.time() - t0:.1f}s", flush=True)
        if not stats.get("candidates"):
            print("NO_CANDIDATES", flush=True)
            return 1
        if not stats.get("updated"):
            print("STALLED_ZERO_UPDATED", flush=True)
            return 1

    print("MAX_ROUNDS", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
