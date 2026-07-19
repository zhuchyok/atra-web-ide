#!/usr/bin/env python3
"""
Controlled replay for recovered incidents into knowledge_nodes.

Default mode is dry-run:
  python3 scripts/replay_recovered_incidents.py

Apply mode:
  python3 scripts/replay_recovered_incidents.py --apply

Environment:
  DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import asyncpg


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "docs" / "recovery" / "recovered_incidents_validated.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "recovery" / "replay_runs"

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay recovered incidents into knowledge_nodes.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to validated incidents jsonl.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for replay artifacts.",
    )
    parser.add_argument("--apply", action="store_true", help="Execute inserts. Without this flag script is dry-run.")
    parser.add_argument(
        "--min-confidence",
        default="high",
        choices=["low", "medium", "high"],
        help="Replay only incidents with confidence >= this threshold.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of records (0 = no limit).")
    parser.add_argument("--run-id", default="", help="Optional explicit run id for artifacts.")
    return parser.parse_args()


def confidence_rank(value: str) -> int:
    ranks = {"low": 1, "medium": 2, "high": 3}
    return ranks.get((value or "").lower(), 0)


def parse_ts(value: str) -> dt.datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(normalized)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return parsed


def source_hash(record: Dict[str, Any]) -> str:
    key = "|".join(
        [
            str(record.get("ts", "")),
            str(record.get("incident_class", "")),
            str(record.get("severity", "")),
            str(record.get("summary", "")),
            str(record.get("evidence_ref", "")),
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def load_records(path: Path, min_confidence: str, limit: int) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    min_rank = confidence_rank(min_confidence)
    selected: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if confidence_rank(rec.get("confidence", "")) < min_rank:
                continue
            rec["_source_hash"] = source_hash(rec)
            selected.append(rec)
            if limit > 0 and len(selected) >= limit:
                break
    return selected


def build_content(record: Dict[str, Any]) -> str:
    return (
        "Recovered historical incident for post-loss continuity.\n"
        f"- Timestamp: {record.get('ts', '')}\n"
        f"- Class: {record.get('incident_class', '')}\n"
        f"- Severity: {record.get('severity', '')}\n"
        f"- Summary: {record.get('summary', '')}\n"
        f"- Evidence: {record.get('evidence_ref', '')}\n"
        f"- Confidence: {record.get('confidence', '')}\n"
    )


def build_metadata(record: Dict[str, Any], run_id: str) -> Dict[str, Any]:
    return {
        "type": "recovery_incident",
        "source": "recovered_incidents_validated",
        "recovery_replay": True,
        "recovery_run_id": run_id,
        "recovery_source_hash": record["_source_hash"],
        "incident_class": record.get("incident_class"),
        "incident_severity": record.get("severity"),
        "incident_confidence": record.get("confidence"),
        "incident_ts": record.get("ts"),
        "evidence_ref": record.get("evidence_ref"),
        "summary": record.get("summary"),
        "reconstructed": bool(record.get("reconstructed", False)),
    }


async def classify_records(conn: asyncpg.Connection, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not records:
        return [], []

    hashes = [r["_source_hash"] for r in records]
    rows = await conn.fetch(
        """
        SELECT metadata->>'recovery_source_hash' AS source_hash
        FROM knowledge_nodes
        WHERE metadata->>'type' = 'recovery_incident'
          AND metadata->>'recovery_source_hash' = ANY($1::text[])
        """,
        hashes,
    )
    existing = {r["source_hash"] for r in rows if r["source_hash"]}

    to_insert: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    for rec in records:
        if rec["_source_hash"] in existing:
            skipped.append(rec)
        else:
            to_insert.append(rec)
    return to_insert, skipped


async def apply_replay(
    conn: asyncpg.Connection,
    records: List[Dict[str, Any]],
    run_id: str,
    output_dir: Path,
) -> Dict[str, Any]:
    inserted: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    for rec in records:
        metadata = build_metadata(rec, run_id)
        content = build_content(rec)
        try:
            created_at = parse_ts(str(rec.get("ts", dt.datetime.now(dt.timezone.utc).isoformat())))
            row = await conn.fetchrow(
                """
                INSERT INTO knowledge_nodes (
                    content,
                    metadata,
                    confidence_score,
                    is_verified,
                    usage_count,
                    created_at,
                    source_ref
                )
                VALUES ($1, $2::jsonb, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                content,
                json.dumps(metadata, ensure_ascii=False),
                0.95,
                True,
                0,
                created_at,
                str(rec.get("evidence_ref", "")),
            )
            inserted.append(
                {
                    "id": str(row["id"]),
                    "source_hash": rec["_source_hash"],
                    "ts": rec.get("ts"),
                    "summary": rec.get("summary"),
                }
            )
        except Exception as exc:  # noqa: BLE001
            failed.append(
                {
                    "source_hash": rec["_source_hash"],
                    "ts": rec.get("ts"),
                    "summary": rec.get("summary"),
                    "error": str(exc),
                }
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    inserted_path = output_dir / f"{run_id}_inserted.jsonl"
    rollback_path = output_dir / f"{run_id}_rollback.sql"
    failed_path = output_dir / f"{run_id}_failed.jsonl"

    with inserted_path.open("w", encoding="utf-8") as f:
        for row in inserted:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with failed_path.open("w", encoding="utf-8") as f:
        for row in failed:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with rollback_path.open("w", encoding="utf-8") as f:
        f.write("-- Rollback script for recovery replay\n")
        f.write("BEGIN;\n")
        if inserted:
            ids_sql = ", ".join([f"'{row['id']}'::uuid" for row in inserted])
            f.write(f"DELETE FROM knowledge_nodes WHERE id IN ({ids_sql});\n")
        f.write("COMMIT;\n")

    return {
        "inserted_count": len(inserted),
        "failed_count": len(failed),
        "inserted_path": str(inserted_path),
        "failed_path": str(failed_path),
        "rollback_path": str(rollback_path),
    }


async def main() -> None:
    args = parse_args()
    run_id = args.run_id.strip() or dt.datetime.now(dt.timezone.utc).strftime("replay_%Y%m%d_%H%M%S")

    records = load_records(args.input, args.min_confidence, args.limit)
    conn = await asyncpg.connect(DB_URL)
    try:
        to_insert, skipped = await classify_records(conn, records)
        summary = {
            "run_id": run_id,
            "mode": "apply" if args.apply else "dry-run",
            "selected_records": len(records),
            "eligible_for_insert": len(to_insert),
            "already_present": len(skipped),
            "min_confidence": args.min_confidence,
            "limit": args.limit,
        }

        if args.apply and to_insert:
            result = await apply_replay(conn, to_insert, run_id, args.output_dir)
            summary.update(result)
        elif args.apply:
            summary.update(
                {
                    "inserted_count": 0,
                    "failed_count": 0,
                    "inserted_path": "",
                    "failed_path": "",
                    "rollback_path": "",
                }
            )

        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
