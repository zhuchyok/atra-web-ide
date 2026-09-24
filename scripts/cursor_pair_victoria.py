#!/usr/bin/env python3
"""Парный близнец: отдать задачу Виктории, сохранить отчёт, опционально записать урок."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "docs" / "curator_reports"
VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010").rstrip("/")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:secret@localhost:6432/knowledge_os",
)
DOMAIN = "cursor_method"


def _http_json(method: str, url: str, payload: dict | None = None, timeout: float = 90) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def chat_victoria(goal: str) -> str:
    body = _http_json(
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
        timeout=120,
    )
    choices = body.get("choices") or []
    if choices:
        content = ((choices[0] or {}).get("message") or {}).get("content")
        if content:
            return str(content)
    raise RuntimeError(f"empty chat completions: {body!r}"[:400])


def write_report(goal: str, answer: str, lesson: str) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
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
    args = parser.parse_args()
    try:
        answer = chat_victoria(args.goal)
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
