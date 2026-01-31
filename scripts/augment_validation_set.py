#!/usr/bin/env python3
"""
Расширение validation set реальными запросами.
Использование: python3 scripts/augment_validation_set.py --real data/real_queries.json --add 10
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict

REPO_ROOT = Path(__file__).resolve().parent.parent

def augment_validation_set(
    validation_path: Path,
    real_queries_path: Path,
    n: int
) -> int:
    """Добавляет топ-N реальных запросов в validation set."""
    with open(validation_path, "r", encoding="utf-8") as f:
        val_data = json.load(f)
    
    queries = val_data.get("queries", val_data) if isinstance(val_data, dict) else val_data
    existing = {q.get("query") or q for q in queries}
    
    with open(real_queries_path, "r", encoding="utf-8") as f:
        real_data = json.load(f)
    
    real_queries = real_data.get("queries", real_data) if isinstance(real_data, dict) else real_data
    
    # Фильтруем новые запросы и сортируем по частоте
    new_candidates = [q for q in real_queries if q.get("query") not in existing]
    new_candidates.sort(key=lambda x: x.get("frequency", 0), reverse=True)
    
    selected = new_candidates[:n]
    added = 0
    
    for item in selected:
        query_text = item.get("query")
        if not query_text or len(query_text) < 5:
            continue
        queries.append({
            "id": f"real_{len(queries) + 1}",
            "query": query_text,
            "reference": None,  # TODO: добавить вручную или через LLM
            "context_expected": [],
            "source": "production",
            "frequency": item.get("frequency", 1)
        })
        added += 1
    
    # Сохраняем
    if isinstance(val_data, dict):
        val_data["queries"] = queries
        val_data["updated"] = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    else:
        val_data = queries
    
    with open(validation_path, "w", encoding="utf-8") as f:
        json.dump(val_data, f, indent=2, ensure_ascii=False)
    
    return added

def main():
    parser = argparse.ArgumentParser(description="Augment validation set with real queries")
    parser.add_argument("--validation", default="data/validation_queries.json")
    parser.add_argument("--real", default="data/real_queries.json")
    parser.add_argument("--add", type=int, default=10, help="Number of queries to add")
    args = parser.parse_args()

    val_path = REPO_ROOT / args.validation
    real_path = REPO_ROOT / args.real
    
    if not val_path.exists():
        print(f"❌ Validation set not found: {val_path}")
        return 1
    
    if not real_path.exists():
        print(f"⚠️ Real queries not found: {real_path}")
        print("Запустите сначала: python3 scripts/collect_real_queries.py")
        return 1
    
    added = augment_validation_set(val_path, real_path, args.add)
    print(f"✅ Добавлено {added} запросов в validation set: {val_path}")
    print("⚠️ Не забудьте добавить reference ответы вручную для новых запросов!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
