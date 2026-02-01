#!/usr/bin/env python3
"""
Объединение источников validation set с дедупликацией.
Рекомендации Data Engineer: единый источник, дедупликация по ключу, полнота данных.
Использование:
  python3 scripts/merge_validation_sources.py
  python3 scripts/merge_validation_sources.py --synthetic data/synthetic_query_variations.json --add 20
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent


def normalize_key(q: str) -> str:
    """Ключ для дедупликации: нижний регистр, сжатие пробелов (Data Engineer)."""
    return " ".join((q or "").lower().split()).strip()


def load_queries(path: Path) -> List[Dict[str, Any]]:
    """Загружает список запросов из JSON (validation или real/synthetic)."""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("queries", data) if isinstance(data, dict) else data


def merge_with_dedupe(
    base_queries: List[Dict[str, Any]],
    extra_sources: List[Tuple[Path, int]],
) -> List[Dict[str, Any]]:
    """
    Объединяет base + дополнительные источники с дедупликацией по normalize_key(query).
    extra_sources: список (path, max_add) — из каждого файла добавить не более max_add новых.
    """
    seen: Set[str] = set()
    result: List[Dict[str, Any]] = []
    for item in base_queries:
        q = item.get("query")
        if q:
            key = normalize_key(q)
            if key not in seen:
                seen.add(key)
                result.append(dict(item))
    for path, max_add in extra_sources:
        extra = load_queries(path)
        added_here = 0
        for item in extra:
            if added_here >= max_add:
                break
            q = item.get("query")
            if not q or len(q) < 3:
                continue
            key = normalize_key(q)
            if key in seen:
                continue
            seen.add(key)
            # Привести к формату validation (id, query, reference, context_expected)
            entry = {
                "id": item.get("id", f"merged_{len(result)+1}"),
                "query": q,
                "reference": item.get("reference"),
                "context_expected": item.get("context_expected", []),
            }
            if item.get("source"):
                entry["source"] = item["source"]
            if item.get("frequency"):
                entry["frequency"] = item["frequency"]
            result.append(entry)
            added_here += 1
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge validation sources with deduplication (Data Engineer)"
    )
    parser.add_argument(
        "--validation",
        default="data/validation_queries.json",
        help="Base validation set",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path (default: overwrite --validation)",
    )
    parser.add_argument(
        "--real",
        default="data/real_queries.json",
        help="Real queries from logs",
    )
    parser.add_argument(
        "--add-real",
        type=int,
        default=15,
        help="Max real queries to add",
    )
    parser.add_argument(
        "--synthetic",
        default="data/synthetic_query_variations.json",
        help="Synthetic variations",
    )
    parser.add_argument(
        "--add-synthetic",
        type=int,
        default=50,
        help="Max synthetic variations to add",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print counts, do not write",
    )
    args = parser.parse_args()

    base_path = REPO_ROOT / args.validation
    if not base_path.exists():
        print(f"❌ Validation set not found: {base_path}", file=sys.stderr)
        return 1

    base_queries = load_queries(base_path)
    extra_sources: List[Tuple[Path, int]] = []
    if (REPO_ROOT / args.real).exists():
        extra_sources.append((REPO_ROOT / args.real, args.add_real))
    if (REPO_ROOT / args.synthetic).exists():
        extra_sources.append((REPO_ROOT / args.synthetic, args.add_synthetic))

    merged = merge_with_dedupe(base_queries, extra_sources)
    print(f"📊 Базовый set: {len(base_queries)} запросов")
    print(f"   После объединения и дедупликации: {len(merged)} запросов")

    if args.dry_run:
        print("   (dry-run: файл не изменён)")
        return 0

    out_path = REPO_ROOT / (args.output or args.validation)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": "Validation set для оценки качества RAG (Фаза 4). reference = эталонный ответ.",
        "version": "1.0",
        "updated": __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
        "queries": merged,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"✅ Сохранено: {out_path}")
    print("💡 Заполните reference для записей с source=production или source=synthetic_variation (если пусто).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
