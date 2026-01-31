#!/usr/bin/env python3
"""
Сбор реальных запросов из production логов для расширения validation set.
Использование: python3 scripts/collect_real_queries.py --days 7 --limit 100
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

REPO_ROOT = Path(__file__).resolve().parent.parent

def collect_from_logs(log_dir: Path, days: int, limit: int):
    """Собирает запросы из текстовых логов."""
    queries = []
    cutoff = datetime.now() - timedelta(days=days)
    
    if not log_dir.exists():
        print(f"⚠️ Каталог логов не найден: {log_dir}")
        return []
    
    # Ищем файлы логов чата
    for log_file in log_dir.glob("**/chat*.log"):
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    # Ищем строки с запросами (примерный паттерн)
                    if '"query":' in line or 'User query:' in line or 'mode=ask' in line:
                        queries.append(line.strip())
        except Exception:
            continue
    
    # Подсчёт частоты (упрощённо)
    freq = Counter(queries)
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
    print("\n💡 Совет: Добавьте топ запросов в validation_queries.json вручную с reference ответами.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
