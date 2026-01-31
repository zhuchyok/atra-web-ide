#!/usr/bin/env python3
"""
Анализ запросов с низким relevance (Фаза 4.1).
Использование: python scripts/analyze_low_relevance.py
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parent.parent


def analyze_problematic_queries(
    report_path: str = "backend/validation_report.json",
    threshold: float = 0.8,
):
    """Анализ запросов с низким relevance."""
    path = REPO_ROOT / report_path
    if not path.exists():
        print(f"❌ Отчёт не найден: {path}")
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    problematic = []
    for result in data.get("results", []):
        m = result.get("metrics", {})
        rel = m.get("relevance", 1.0)
        if rel < threshold:
            problematic.append({
                "query": result["query"],
                "relevance": rel,
                "faithfulness": m.get("faithfulness", 0),
                "coherence": m.get("coherence", 0),
                "bleu": m.get("bleu", 0),
                "rouge": m.get("rouge", 0),
            })

    print(f"📊 Анализ отчёта: {path.name}")
    print(f"   Всего запросов: {len(data.get('results', []))}")
    print(f"   Проблемных (relevance < {threshold:.0%}): {len(problematic)}")
    print("=" * 60)

    # Группируем по типам
    patterns = defaultdict(list)
    for item in problematic:
        q = item["query"].lower()
        words = len(q.split())
        if item["relevance"] == 0:
            patterns["критичные_0_relevance"].append(item)
        elif words <= 3:
            patterns["короткие"].append(item)
        elif any(w in q for w in ["как", "почему", "зачем"]):
            patterns["многошаговые"].append(item)
        elif any(w in q for w in ["лучше", "сравни", "рекомендуй"]):
            patterns["абстрактные"].append(item)
        else:
            patterns["прочие"].append(item)

    for pattern, items in sorted(patterns.items()):
        if items:
            avg_rel = sum(i["relevance"] for i in items) / len(items)
            print(f"\n🔍 {pattern}: {len(items)} запросов, avg relevance: {avg_rel:.1%}")
            for i in items[:5]:
                print(f"   • '{i['query']}' → rel={i['relevance']:.2f} faith={i['faithfulness']:.2f} coh={i['coherence']:.2f}")

    # Сохраняем для дальнейшего анализа
    out_path = REPO_ROOT / "problematic_queries_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "threshold": threshold,
            "total_problematic": len(problematic),
            "patterns": {k: v for k, v in patterns.items() if v},
            "all": problematic,
        }, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Сохранено: {out_path}")

    return problematic


def main():
    threshold = 0.8
    if len(sys.argv) > 1:
        try:
            threshold = float(sys.argv[1])
        except ValueError:
            pass
    analyze_problematic_queries(threshold=threshold)
    return 0


if __name__ == "__main__":
    sys.exit(main())
