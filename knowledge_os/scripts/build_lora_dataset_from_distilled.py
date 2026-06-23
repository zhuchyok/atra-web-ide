#!/usr/bin/env python3
"""
Build LoRA training/eval dataset from distilled knowledge nodes.

Professional defaults:
- Use only nodes with metadata.distilled=true
- Enforce minimum content length
- Keep deterministic train/eval split
- Emit manifest for quality gates
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import asyncpg

DEFAULT_DB_URL = "postgresql://admin:secret@localhost:6432/knowledge_os"


def _stable_bucket(node_id: str, eval_pct: int) -> str:
    digest = hashlib.sha256(node_id.encode("utf-8")).hexdigest()
    val = int(digest[:8], 16) % 100
    return "eval" if val < eval_pct else "train"


def _build_record(content: str, metadata: dict[str, Any]) -> dict[str, Any]:
    expert = str(metadata.get("expert") or "Виктория")
    source = str(metadata.get("source") or "knowledge_node")
    node_type = str(metadata.get("type") or "general")
    instruction = (
        f"Ты эксперт {expert}. "
        f"Сформулируй профессиональный ответ по материалу ({node_type}) из источника {source}. "
        "Сохрани факты, убери воду, добавь практические шаги."
    )
    return {
        "messages": [
            {"role": "system", "content": "Ты Виктория, инженерный Team Lead корпорации ATRA."},
            {"role": "user", "content": instruction},
            {"role": "assistant", "content": content.strip()},
        ]
    }


def _chunk_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    source = text.strip()
    if not source:
        return []
    if len(source) <= max_chars:
        return [source]

    chunks: list[str] = []
    step = max(1, max_chars - max(0, overlap_chars))
    start = 0
    while start < len(source):
        end = min(len(source), start + max_chars)
        if end < len(source):
            cut = source.rfind(" ", start + int(max_chars * 0.7), end)
            if cut > start:
                end = cut
        part = source[start:end].strip()
        if part:
            chunks.append(part)
        if end >= len(source):
            break
        start = max(0, end - max(0, overlap_chars))
        if start + step <= end:
            start = end
    return chunks


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="knowledge_os/training_data")
    parser.add_argument("--limit", type=int, default=50000)
    parser.add_argument("--min-content-len", type=int, default=180)
    parser.add_argument("--max-content-chars", type=int, default=1600)
    parser.add_argument("--chunk-overlap-chars", type=int, default=160)
    parser.add_argument("--eval-pct", type=int, default=10)
    parser.add_argument("--required-distilled-pct", type=float, default=50.0)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", DEFAULT_DB_URL))
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    train_path = out_dir / "lora_train.jsonl"
    eval_path = out_dir / "lora_eval.jsonl"
    train_alias_path = out_dir / "train.jsonl"
    eval_alias_path = out_dir / "valid.jsonl"
    test_alias_path = out_dir / "test.jsonl"
    manifest_path = out_dir / "lora_dataset_manifest.json"

    conn = await asyncpg.connect(args.database_url)
    try:
        totals = await conn.fetchrow(
            """
            SELECT
              COUNT(*) AS total_nodes,
              COUNT(*) FILTER (WHERE COALESCE(metadata,'{}'::jsonb)->>'distilled'='true') AS distilled_nodes
            FROM knowledge_nodes
            """
        )
        total_nodes = int(totals["total_nodes"] or 0)
        distilled_nodes = int(totals["distilled_nodes"] or 0)
        distilled_pct = (distilled_nodes * 100.0 / total_nodes) if total_nodes else 0.0

        rows = await conn.fetch(
            """
            SELECT id, content, metadata
            FROM knowledge_nodes
            WHERE COALESCE(metadata,'{}'::jsonb)->>'distilled'='true'
              AND content IS NOT NULL
              AND char_length(content) >= $1
            ORDER BY updated_at DESC NULLS LAST
            LIMIT $2
            """,
            args.min_content_len,
            args.limit,
        )
    finally:
        await conn.close()

    train_count = 0
    eval_count = 0
    chunked_samples = 0
    with (
        train_path.open("w", encoding="utf-8") as train_f,
        eval_path.open("w", encoding="utf-8") as eval_f,
    ):
        for r in rows:
            node_id = str(r["id"])
            content = str(r["content"] or "").strip()
            meta = r["metadata"] if isinstance(r["metadata"], dict) else {}
            parts = _chunk_text(content, args.max_content_chars, args.chunk_overlap_chars)
            if len(parts) > 1:
                chunked_samples += len(parts) - 1
            for idx, part in enumerate(parts):
                record = _build_record(part, meta)
                line = json.dumps(record, ensure_ascii=False)
                sample_id = f"{node_id}:{idx}"
                if _stable_bucket(sample_id, args.eval_pct) == "eval":
                    eval_f.write(line + "\n")
                    eval_count += 1
                else:
                    train_f.write(line + "\n")
                    train_count += 1

    # Keep standard aliases for tools expecting train.jsonl/valid.jsonl naming.
    train_alias_path.write_text(train_path.read_text(encoding="utf-8"), encoding="utf-8")
    eval_alias_path.write_text(eval_path.read_text(encoding="utf-8"), encoding="utf-8")
    test_alias_path.write_text(eval_path.read_text(encoding="utf-8"), encoding="utf-8")

    manifest = {
        "total_nodes": total_nodes,
        "distilled_nodes": distilled_nodes,
        "distilled_pct": round(distilled_pct, 3),
        "required_distilled_pct": args.required_distilled_pct,
        "is_distillation_gate_passed": distilled_pct >= args.required_distilled_pct,
        "min_content_len": args.min_content_len,
        "max_content_chars": args.max_content_chars,
        "chunk_overlap_chars": args.chunk_overlap_chars,
        "input_rows_used": len(rows),
        "extra_chunked_samples": chunked_samples,
        "train_samples": train_count,
        "eval_samples": eval_count,
        "paths": {
            "train_jsonl": str(train_path),
            "eval_jsonl": str(eval_path),
            "train_alias_jsonl": str(train_alias_path),
            "eval_alias_jsonl": str(eval_alias_path),
            "test_alias_jsonl": str(test_alias_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
