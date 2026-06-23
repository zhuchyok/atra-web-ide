import asyncio
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone

import asyncpg

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:secret@localhost:6432/knowledge_os",
)
WORKSPACE = os.getenv("CURSOR_WORKSPACE", "/Users/bikos/Documents/atra-web-ide")
MODEL = os.getenv("CURSOR_MODEL", "gemini-3-flash")
TARGET = int(os.getenv("DISTILL_TARGET_NODES", "5000"))
CLAIM_BATCH = int(os.getenv("DISTILL_CLAIM_BATCH", "20"))
MAX_RETRIES = int(os.getenv("DISTILL_MAX_RETRIES", "3"))
RETRY_BASE_SECONDS = int(os.getenv("DISTILL_RETRY_BASE_SECONDS", "300"))
CURSOR_TIMEOUT_SEC = int(os.getenv("CURSOR_DISTILL_TIMEOUT_SEC", "180"))
CURSOR_DISTILL_CONCURRENCY = max(1, int(os.getenv("CURSOR_DISTILL_CONCURRENCY", "4")))
DB_OP_RETRIES = max(1, int(os.getenv("DISTILL_DB_OP_RETRIES", "5")))
DB_RETRY_BASE_SEC = float(os.getenv("DISTILL_DB_RETRY_BASE_SEC", "0.5"))

ELIGIBLE_SQL = """
SELECT id::text, content, COALESCE(metadata, '{}'::jsonb)::text AS metadata_str
FROM knowledge_nodes
WHERE content IS NOT NULL
  AND (metadata->>'distilled' IS NULL OR metadata->>'distilled'='false')
  AND COALESCE(metadata->>'distill_status', 'pending') != 'failed'
  AND COALESCE(metadata->>'distill_status', 'pending') != 'in_progress'
  AND (
      metadata->>'distill_status' IS DISTINCT FROM 'retry'
      OR COALESCE((metadata->>'distill_next_retry_ts')::bigint, 0) <= EXTRACT(EPOCH FROM NOW())::bigint
  )
ORDER BY
  CASE WHEN confidence_score < 0.5 THEN 0 ELSE 1 END ASC,
  confidence_score DESC,
  created_at DESC
LIMIT $1
"""


CLAIM_SQL = """
WITH candidates AS (
    SELECT id
    FROM knowledge_nodes
    WHERE content IS NOT NULL
      AND (metadata->>'distilled' IS NULL OR metadata->>'distilled'='false')
      AND COALESCE(metadata->>'distill_status', 'pending') != 'failed'
      AND COALESCE(metadata->>'distill_status', 'pending') != 'in_progress'
      AND (
          metadata->>'distill_status' IS DISTINCT FROM 'retry'
          OR COALESCE((metadata->>'distill_next_retry_ts')::bigint, 0) <= EXTRACT(EPOCH FROM NOW())::bigint
      )
    ORDER BY
      CASE WHEN confidence_score < 0.5 THEN 0 ELSE 1 END ASC,
      confidence_score DESC,
      created_at DESC
    LIMIT $1
    FOR UPDATE SKIP LOCKED
),
claimed AS (
    UPDATE knowledge_nodes kn
    SET metadata = COALESCE(kn.metadata, '{}'::jsonb) || $2::jsonb
    FROM candidates c
    WHERE kn.id = c.id
    RETURNING kn.id::text AS id, kn.content, COALESCE(kn.metadata, '{}'::jsonb)::text AS metadata_str
)
SELECT id, content, metadata_str
FROM claimed
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_connection_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            asyncpg.exceptions.ConnectionDoesNotExistError,
            asyncpg.exceptions.ConnectionFailureError,
            asyncpg.exceptions.InterfaceError,
            ConnectionError,
            OSError,
        ),
    )


def _parse_update_count(status: str) -> int:
    # asyncpg execute() usually returns e.g. "UPDATE 1"
    try:
        return int(str(status).rsplit(" ", 1)[-1])
    except Exception:
        return 0


async def _connect_db() -> asyncpg.Connection:
    return await asyncpg.connect(DB_URL)


async def _db_execute(state: dict, query: str, *args) -> str:
    last_exc: Exception | None = None
    for attempt in range(1, DB_OP_RETRIES + 1):
        try:
            if not state.get("conn") or state["conn"].is_closed():
                state["conn"] = await _connect_db()
            return await state["conn"].execute(query, *args)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if not _is_connection_error(exc):
                raise
            try:
                if state.get("conn") and not state["conn"].is_closed():
                    await state["conn"].close()
            except Exception:
                pass
            state["conn"] = None
            await asyncio.sleep(min(DB_RETRY_BASE_SEC * (2 ** (attempt - 1)), 5.0))
    raise RuntimeError(f"db_execute_failed_after_retries: {last_exc}")


async def _db_fetch(state: dict, query: str, *args):
    last_exc: Exception | None = None
    for attempt in range(1, DB_OP_RETRIES + 1):
        try:
            if not state.get("conn") or state["conn"].is_closed():
                state["conn"] = await _connect_db()
            return await state["conn"].fetch(query, *args)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if not _is_connection_error(exc):
                raise
            try:
                if state.get("conn") and not state["conn"].is_closed():
                    await state["conn"].close()
            except Exception:
                pass
            state["conn"] = None
            await asyncio.sleep(min(DB_RETRY_BASE_SEC * (2 ** (attempt - 1)), 5.0))
    raise RuntimeError(f"db_fetch_failed_after_retries: {last_exc}")


async def _db_fetchval(state: dict, query: str, *args):
    last_exc: Exception | None = None
    for attempt in range(1, DB_OP_RETRIES + 1):
        try:
            if not state.get("conn") or state["conn"].is_closed():
                state["conn"] = await _connect_db()
            return await state["conn"].fetchval(query, *args)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if not _is_connection_error(exc):
                raise
            try:
                if state.get("conn") and not state["conn"].is_closed():
                    await state["conn"].close()
            except Exception:
                pass
            state["conn"] = None
            await asyncio.sleep(min(DB_RETRY_BASE_SEC * (2 ** (attempt - 1)), 5.0))
    raise RuntimeError(f"db_fetchval_failed_after_retries: {last_exc}")


def _extract_json(raw: str) -> dict:
    text = (raw or "").strip()
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    m = re.search(r"(\{.*\})", text, re.DOTALL)
    if m:
        candidate = re.sub(r",\s*([}\]])", r"\1", m.group(1))
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    raise ValueError("no_json")


def _fallback_wisdom(raw_text: str, content: str) -> dict:
    basis = (raw_text or "").strip() or (content or "").strip()
    summary = re.sub(r"\s+", " ", basis)[:220].strip()
    if len(summary) > 200:
        summary = summary[:197].rstrip() + "..."
    if not summary:
        summary = "Краткий вывод по узлу знаний сформирован."
    return {
        "wisdom_summary": summary,
        "instruction": "Использовать как сжатый контекст и сверять с первоисточником перед применением.",
        "category": "strategy",
    }


async def _cursor_distill(content: str) -> tuple[dict | None, str]:
    prompt = f"""
SYSTEM: You are a strict knowledge distiller. Return only valid JSON with keys:
wisdom_summary, instruction, category.

Rules:
- wisdom_summary: one concise sentence
- instruction: one actionable command
- category: one of coding|strategy|ops|research
- Output ONLY JSON, no markdown

INPUT:
{content}
""".strip()

    def _run_cursor_once() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "cursor",
                "agent",
                "--print",
                "--trust",
                "--workspace",
                WORKSPACE,
                "--model",
                MODEL,
                "--output-format",
                "text",
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=CURSOR_TIMEOUT_SEC,
            check=False,
        )

    try:
        result = await asyncio.to_thread(_run_cursor_once)
    except subprocess.TimeoutExpired:
        return None, "cursor_timeout"
    except Exception as exc:
        return None, f"cursor_exec_error:{str(exc)[:180]}"

    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode != 0:
        return None, f"cursor_rc_{result.returncode}:{err[:180]}"

    try:
        parsed = _extract_json(out)
    except Exception:
        parsed = _fallback_wisdom(out, content)
    return parsed, ""


async def _mark_done(state: dict, node_id: str, wisdom: dict) -> bool:
    summary = str(wisdom.get("wisdom_summary", "")).strip()
    instruction = str(wisdom.get("instruction", "")).strip()
    category = str(wisdom.get("category", "strategy")).strip().lower() or "strategy"
    if category not in {"coding", "strategy", "ops", "research"}:
        category = "strategy"

    patch = {
        "distilled": "true",
        "distilled_at": _now_iso(),
        "wisdom_summary": summary,
        "instruction": instruction,
        "category": category,
        "distilled_by": f"cursor:{MODEL}",
        "distill_status": "done",
        "distill_last_error": "",
        "distill_attempts": 0,
        "distill_next_retry_ts": 0,
    }
    status = await _db_execute(
        state,
        """
        UPDATE knowledge_nodes
        SET metadata = COALESCE(metadata, '{}'::jsonb) || $1::jsonb
        WHERE id = $2::uuid
        """,
        json.dumps(patch),
        node_id,
    )
    return _parse_update_count(status) == 1


async def _mark_retry_or_failed(state: dict, node_id: str, metadata_str: str, reason: str) -> bool:
    try:
        metadata = json.loads(metadata_str or "{}")
    except Exception:
        metadata = {}
    attempts = int(metadata.get("distill_attempts", 0)) + 1
    next_retry = int(time.time()) + min(RETRY_BASE_SECONDS * (2 ** (attempts - 1)), 3600)
    status = "failed" if attempts >= MAX_RETRIES else "retry"
    patch = {
        "distilled": "false",
        "distill_status": status,
        "distill_attempts": attempts,
        "distill_last_error": reason[:240],
        "distill_last_attempt_at": _now_iso(),
        "distill_next_retry_ts": next_retry,
    }
    status = await _db_execute(
        state,
        """
        UPDATE knowledge_nodes
        SET metadata = COALESCE(metadata, '{}'::jsonb) || $1::jsonb
        WHERE id = $2::uuid
        """,
        json.dumps(patch),
        node_id,
    )
    return _parse_update_count(status) == 1


async def _count_eligible(state: dict) -> int:
    val = await _db_fetchval(
        state,
        """
        SELECT COUNT(*)
        FROM knowledge_nodes
        WHERE content IS NOT NULL
          AND (metadata->>'distilled' IS NULL OR metadata->>'distilled'='false')
          AND COALESCE(metadata->>'distill_status', 'pending') != 'failed'
          AND (
              metadata->>'distill_status' IS DISTINCT FROM 'retry'
              OR COALESCE((metadata->>'distill_next_retry_ts')::bigint, 0) <= EXTRACT(EPOCH FROM NOW())::bigint
          )
        """
    )
    return int(val or 0)


async def main() -> None:
    state = {"conn": await _connect_db()}
    start_pending = await _count_eligible(state)
    print(
        f"START_CURSOR model={MODEL} target={TARGET} pending={start_pending} batch={CLAIM_BATCH}",
        flush=True,
    )

    processed = 0
    cycle = 0

    while processed < TARGET:
        claim_patch = {
            "distill_status": "in_progress",
            "distill_started_at": _now_iso(),
            "distill_owner": "cursor_campaign",
        }
        rows = await _db_fetch(state, CLAIM_SQL, CLAIM_BATCH, json.dumps(claim_patch))
        if not rows:
            print("STOP no_eligible_rows", flush=True)
            break

        cycle += 1
        cycle_done = 0
        cycle_rows = []
        for row in rows:
            node_id = row["id"]
            content = row["content"] or ""
            metadata_str = row["metadata_str"] or "{}"
            print(
                f"NODE_CURSOR cycle={cycle} node={node_id} processed={processed}/{TARGET}",
                flush=True,
            )
            cycle_rows.append((node_id, content, metadata_str))
            if processed + len(cycle_rows) >= TARGET:
                break

        # Run Cursor calls concurrently with bounded parallelism for better throughput.
        sem = asyncio.Semaphore(CURSOR_DISTILL_CONCURRENCY)

        async def _run_one(node_id: str, content: str, metadata_str: str):
            async with sem:
                wisdom, error = await _cursor_distill(content)
                return node_id, metadata_str, wisdom, error

        tasks = [
            asyncio.create_task(_run_one(node_id, content, metadata_str))
            for node_id, content, metadata_str in cycle_rows
        ]

        for task in asyncio.as_completed(tasks):
            node_id, metadata_str, wisdom, error = await task
            if wisdom:
                updated = await _mark_done(state, node_id, wisdom)
                if updated:
                    processed += 1
                    cycle_done += 1
                    print(
                        f"NODE_DONE_CURSOR cycle={cycle} node={node_id} done={processed}/{TARGET}",
                        flush=True,
                    )
                else:
                    print(f"NODE_SKIP_CURSOR cycle={cycle} node={node_id} reason=done_update_failed", flush=True)
            else:
                updated = await _mark_retry_or_failed(state, node_id, metadata_str, error or "cursor_error")
                if updated:
                    print(
                        f"NODE_RETRY_CURSOR cycle={cycle} node={node_id} reason={error or 'cursor_error'}",
                        flush=True,
                    )
                else:
                    print(f"NODE_SKIP_CURSOR cycle={cycle} node={node_id} reason=retry_update_failed", flush=True)

        pending = await _count_eligible(state)
        print(
            f"PROGRESS_CURSOR cycle={cycle} done={processed}/{TARGET} cycle_done={cycle_done} pending={pending}",
            flush=True,
        )
        if cycle_done == 0:
            print("STOP no_progress_in_cycle", flush=True)
            break

    final_pending = await _count_eligible(state)
    print(f"FINAL_CURSOR done={processed} pending={final_pending}", flush=True)
    if state.get("conn") and not state["conn"].is_closed():
        await state["conn"].close()


if __name__ == "__main__":
    asyncio.run(main())
