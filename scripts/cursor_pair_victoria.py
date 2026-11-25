#!/usr/bin/env python3
"""Парный близнец: отдать задачу Виктории, сохранить отчёт, опционально записать урок.

Primary path: POST /run?async_mode=true + poll /run/status/{task_id}
(so curator fact-checks get real answers, not 35s chat handoff stubs).

Fallback: /v1/chat/completions (short goals / when /run unavailable).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "docs" / "curator_reports"
VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010").rstrip("/")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:secret@localhost:6432/knowledge_os",
)
DOMAIN = "cursor_method"
DEFAULT_MAX_WAIT = float(os.getenv("CURSOR_PAIR_MAX_WAIT_SEC", "300"))
DEFAULT_MAX_STEPS = int(os.getenv("CURSOR_PAIR_MAX_STEPS", "200"))
POLL_INTERVAL = float(os.getenv("CURSOR_PAIR_POLL_SEC", "2"))


def _http_json(
    method: str,
    url: str,
    payload: dict | None = None,
    timeout: float = 90,
) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            body = json.loads(raw) if raw else {}
            return int(resp.status), body
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {"error": raw[:400]}
        return int(exc.code), body


def run_victoria_async(
    goal: str,
    max_wait: float = DEFAULT_MAX_WAIT,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> str:
    """Designed path: async /run + poll until terminal or timeout."""
    status, data = _http_json(
        "POST",
        f"{VICTORIA_URL}/run?async_mode=true",
        {
            "goal": goal,
            "max_steps": max_steps,
            "project_context": "atra-web-ide",
            "source": "cursor_pair",
        },
        timeout=60,
    )
    if status == 200:
        out = data.get("output") or ""
        if out:
            return str(out)
        raise RuntimeError(f"200 without output: {data!r}"[:400])
    if status != 202:
        raise RuntimeError(f"/run async HTTP {status}: {data!r}"[:400])
    task_id = data.get("task_id")
    if not task_id:
        raise RuntimeError(f"202 without task_id: {data!r}"[:400])

    deadline = time.monotonic() + max_wait
    last = data
    while time.monotonic() < deadline:
        st_code, rec = _http_json(
            "GET",
            f"{VICTORIA_URL}/run/status/{task_id}",
            timeout=30,
        )
        if st_code == 200 and isinstance(rec, dict):
            last = rec
            st = str(rec.get("status") or "").lower()
            if st in ("completed", "success"):
                out = rec.get("output") or ""
                if out:
                    return str(out)
                return "✅ Задача выполнена, но без текстового вывода."
            if st in ("failed", "error", "cancelled"):
                err = rec.get("error") or rec.get("output") or st
                raise RuntimeError(f"victoria {st}: {err}"[:400])
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(
        f"pair poll timeout after {max_wait:.0f}s task_id={task_id} last={last!r}"[:500]
    )


def chat_victoria(goal: str) -> str:
    """Fallback sync chat path (live-fact short answers)."""
    status, body = _http_json(
        "POST",
        f"{VICTORIA_URL}/v1/chat/completions",
        {
            "model": "victoria",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Работай по скиллу cursor-method: факты до вывода, "
                        "не говори готово без доказательства."
                    ),
                },
                {"role": "user", "content": goal},
            ],
            "max_tokens": 800,
        },
        timeout=180,
    )
    if status != 200:
        raise RuntimeError(f"chat HTTP {status}: {body!r}"[:400])
    choices = body.get("choices") or []
    if choices:
        content = ((choices[0] or {}).get("message") or {}).get("content")
        if content:
            return str(content)
    raise RuntimeError(f"empty chat completions: {body!r}"[:400])


def ask_victoria(goal: str, prefer_async: bool = True, max_wait: float = DEFAULT_MAX_WAIT) -> str:
    if prefer_async:
        try:
            return run_victoria_async(goal, max_wait=max_wait)
        except (URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            print(f"WARN /run async failed, retry once: {exc}", file=sys.stderr)
            try:
                return run_victoria_async(
                    goal, max_wait=max(max_wait, 180.0), max_steps=DEFAULT_MAX_STEPS
                )
            except (URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc2:
                print(f"WARN /run async retry failed, fallback chat: {exc2}", file=sys.stderr)
    return chat_victoria(goal)


def write_report(goal: str, answer: str, lesson: str) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S-%f")
    path = REPORTS / f"pair_{stamp}.md"
    path.write_text(
        f"# Pair {stamp}\n\n## Goal\n\n{goal}\n\n## Victoria\n\n{answer}\n\n## Lesson\n\n{lesson}\n",
        encoding="utf-8",
    )
    (REPORTS / f"pair_{stamp}.json").write_text(
        json.dumps(
            {"goal": goal, "answer": answer, "lesson": lesson, "ts": stamp},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def write_lesson(goal: str, answer: str, lesson: str) -> str:
    try:
        import asyncio

        import asyncpg
    except ImportError:
        return _write_lesson_psql(goal, answer, lesson)

    async def _insert() -> str:
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = $1", DOMAIN)
            if not domain_id:
                domain_id = await conn.fetchval(
                    "INSERT INTO domains (name, description) VALUES ($1, $2) RETURNING id",
                    DOMAIN,
                    "Уроки парного ученичества Cursor → Victoria",
                )
            content = (
                f"Урок cursor_method. Задача: {goal[:400]}\n"
                f"Как сделал бы Cursor: {lesson}\n"
                f"Что ответила Victoria (срез): {answer[:600]}"
            )
            node_id = await conn.fetchval(
                """
                INSERT INTO knowledge_nodes
                    (domain_id, content, confidence_score, metadata, source_ref)
                VALUES ($1, $2, $3, $4::jsonb, $5)
                RETURNING id
                """,
                domain_id,
                content,
                0.9,
                json.dumps({"source": "cursor_pair", "domain": DOMAIN}),
                "cursor_pair",
            )
            return str(node_id)
        finally:
            await conn.close()

    try:
        return asyncio.run(_insert())
    except Exception:
        return _write_lesson_psql(goal, answer, lesson)


def _write_lesson_psql(goal: str, answer: str, lesson: str) -> str:
    import subprocess

    content = (
        f"Урок cursor_method. Задача: {goal[:400]} "
        f"Как сделал бы Cursor: {lesson} "
        f"Что ответила Victoria (срез): {answer[:400]}"
    ).replace("'", "''")
    sql = (
        "INSERT INTO domains (name, description) SELECT 'cursor_method', "
        "'Уроки парного ученичества Cursor → Victoria' "
        "WHERE NOT EXISTS (SELECT 1 FROM domains WHERE name = 'cursor_method'); "
        "INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, source_ref) "
        "SELECT id, '" + content + "', 0.9, "
        "'{\"source\":\"cursor_pair\"}'::jsonb, 'cursor_pair' "
        "FROM domains WHERE name = 'cursor_method' RETURNING id;"
    )
    proc = subprocess.run(
        [
            "docker",
            "exec",
            "knowledge_postgres",
            "psql",
            "-U",
            "admin",
            "-d",
            "knowledge_os",
            "-tAc",
            sql,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "psql failed")
    return proc.stdout.strip() or "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="Отдать близнец Виктории и записать урок")
    parser.add_argument("--goal", required=True, help="Текст близнеца")
    parser.add_argument("--lesson", default="", help="Как сделал бы Cursor / что она пропустила")
    parser.add_argument(
        "--chat-only",
        action="store_true",
        help="Только /v1/chat/completions (без /run async)",
    )
    parser.add_argument(
        "--max-wait",
        type=float,
        default=DEFAULT_MAX_WAIT,
        help="Макс. ожидание poll /run/status (сек)",
    )
    args = parser.parse_args()
    try:
        answer = ask_victoria(
            args.goal,
            prefer_async=not args.chat_only,
            max_wait=args.max_wait,
        )
    except (URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"FAIL channel: {exc}", file=sys.stderr)
        return 2
    path = write_report(args.goal, answer, args.lesson)
    node = ""
    if args.lesson.strip():
        try:
            node = write_lesson(args.goal, answer, args.lesson)
        except Exception as exc:  # noqa: BLE001 — отчёт уже есть
            node = f"lesson write failed: {exc}"
    print(f"OK report={path}")
    if node:
        print(f"OK lesson={node}")
    print(answer[:1200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
