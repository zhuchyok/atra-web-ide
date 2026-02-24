#!/usr/bin/env python3
"""
Сбор реальных запросов из production логов для расширения validation set.
Рекомендации Data Engineer: нормализация, дедупликация по ключу, качество данных.
Использование: python3 scripts/collect_real_queries.py --days 7 --limit 100
"""
import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

# Ключи в JSON-логах, откуда извлекаем текст запроса (backend/API, чат)
QUERY_KEYS = ("query", "goal", "message", "content", "text", "user_message")

def normalize_query(text: str) -> str:
    """Нормализация для дедупликации: нижний регистр, сжатие пробелов (Data Engineer)."""
    if not text or not isinstance(text, str):
        return ""
    t = " ".join(text.split()).strip()
    return t.lower() if len(t) >= 2 else t

def extract_query_from_line(line: str) -> Optional[str]:
    """Пытается извлечь текст запроса из JSON-строки лога."""
    line = line.strip()
    if not line:
        return None
    # Попытка распарсить как JSON (целиком или в конце строки)
    for candidate in (line, line.split("\t")[-1], line.split(" - ")[-1]):
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                for key in QUERY_KEYS:
                    val = obj.get(key)
                    if isinstance(val, str) and len(val) >= 2:
                        return normalize_query(val)
            elif isinstance(obj, str) and len(obj) >= 2:
                return normalize_query(obj)
        except (json.JSONDecodeError, TypeError):
            continue
    # Fallback: вытащить значение после "query": "..." или goal": "
    for pat in (r'"query"\s*:\s*"([^"]+)"', r'"goal"\s*:\s*"([^"]+)"', r'"message"\s*:\s*"([^"]+)"'):
        m = re.search(pat, line)
        if m:
            return normalize_query(m.group(1))
    return None

def collect_from_logs(log_dir: Path, days: int, limit: int):
    """Собирает запросы из текстовых и JSON логов с нормализацией."""
    raw_queries = []

    if not log_dir.exists():
        print(f"⚠️ Каталог логов не найден: {log_dir}")
        return []

    for log_file in list(log_dir.glob("**/*.log")) + list(log_dir.glob("**/chat*.json")):
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    extracted = extract_query_from_line(line)
                    if extracted and len(extracted) >= 3:
                        raw_queries.append(extracted)
                    elif any(x in line for x in ('"query":', 'User query:', 'goal":', 'message":')):
                        # Сохраняем нормализованную строку как fallback
                        norm = normalize_query(line)
                        if len(norm) >= 5:
                            raw_queries.append(norm[:500])
        except Exception:
            continue

    freq = Counter(raw_queries)
    top_queries = [{"query": q, "frequency": c, "source": "logs"} for q, c in freq.most_common(limit)]
    return top_queries

def main():
    parser = argparse.ArgumentParser(description="Collect real production queries")
    parser.add_argument("--days", type=int, default=7, help="Days to collect")
    parser.add_argument("--limit", type=int, default=100, help="Max queries")
    parser.add_argument("--output", default="data/real_queries.json")
    args = parser.parse_args()

    log_dir = REPO_ROOT / "logs"
    queries = collect_from_logs(log_dir, args.days, args.limit)

    print(f"📊 Собрано {len(queries)} запросов из логов за {args.days} дней")

    # Сохраняем
    output = Path(args.output)
    if not output.is_absolute():
        output = REPO_ROOT / output

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump({"queries": queries, "collected_at": datetime.now().isoformat()}, f, indent=2, ensure_ascii=False)

    print(f"✅ Сохранено в {output}")
    print("\n💡 Совет (QA): добавьте топ запросов в validation set: python3 scripts/augment_validation_set.py --real data/real_queries.json --add 10")
    print("   Затем заполните reference ответы для новых запросов в data/validation_queries.json.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
