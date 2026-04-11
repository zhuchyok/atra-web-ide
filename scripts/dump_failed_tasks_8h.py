#!/usr/bin/env python3
"""Список failed-задач за последние N часов с текстом для анализа (Victoria / куратор)."""
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone

import asyncpg


async def main(hours: float = 8.0, limit: int = 50) -> None:
    conn = None
    for port in (6432, 5432):
        try:
            conn = await asyncpg.connect(
                f"postgresql://admin:secret@localhost:{port}/knowledge_os"
            )
            break
        except Exception:
            continue
    if not conn:
        print("ERROR: не удалось подключиться к knowledge_os (порты 6432, 5432)", file=sys.stderr)
        sys.exit(1)

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = await conn.fetch(
        """
        SELECT id, title, status, priority, created_at, updated_at,
               description, result, metadata
        FROM tasks
        WHERE status = 'failed' AND updated_at > $1
        ORDER BY updated_at DESC
        LIMIT $2
        """,
        since,
        limit,
    )
    await conn.close()

    print(f"failed за последние {hours} ч: {len(rows)}\n")
    for r in rows:
        meta = r["metadata"] or {}
        err = meta.get("error") if isinstance(meta, dict) else None
        print("=" * 72)
        print("id:", r["id"])
        print("updated_at:", r["updated_at"])
        print("title:", (r["title"] or "")[:300])
        if r["description"]:
            d = (r["description"] or "").strip()
            print("description:", d[:600] + ("…" if len(d) > 600 else ""))
        if r["result"]:
            res = str(r["result"]).strip()
            print("result:", res[:800] + ("…" if len(res) > 800 else ""))
        if err:
            print("metadata.error:", str(err)[:500])
        if isinstance(meta, dict) and meta:
            slim = {k: meta[k] for k in ("trace", "last_error", "exception", "worker") if k in meta}
            if slim:
                print("metadata (фрагмент):", json.dumps(slim, ensure_ascii=False, default=str)[:500])


if __name__ == "__main__":
    h = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    asyncio.run(main(hours=h))
