#!/usr/bin/env python3
"""
Анализ причин низкого coherence (Фаза 4.1).
Использование: python scripts/analyze_coherence_issues.py
"""
import asyncio
import json
import re
import sys
from pathlib import Path
from collections import defaultdict
from typing import Tuple, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))


def _coherence_heuristic(response: str) -> Tuple[float, Dict]:
    """
    Разбор coherence по факторам (повтор логики RAGEvaluator).
    Возвращает (score, breakdown).
    """
    if not response or len(response.strip()) < 10:
        return 0.0, {"len_ok": False, "punct": False, "long": False, "no_spaces": False}
    score = 0.5
    breakdown = {"base": 0.5, "punct": 0, "long": 0, "no_spaces": 0}
    if "." in response or "!" in response or "?" in response:
        score += 0.2
        breakdown["punct"] = 0.2
    if len(response) > 50:
        score += 0.2
        breakdown["long"] = 0.2
    if not re.search(r"\s{5,}", response):
        score += 0.1
        breakdown["no_spaces"] = 0.1
    return min(1.0, score), breakdown


async def fetch_responses_for_queries(queries: List[Dict]) -> Dict[str, str]:
    """Получить реальные ответы RAG для запросов."""
    try:
        from app.services.knowledge_os import KnowledgeOSClient
        from app.services.rag_light import RAGLightService
    except ImportError:
        return {}
    kos = KnowledgeOSClient()
    await kos.connect()
    rag = RAGLightService(knowledge_os=kos)
    results = {}
    for item in queries:
        q = item.get("query", "")
        if not q:
            continue
        try:
            chunk_result = await rag.search_one_chunk(q, limit=1)
            if chunk_result:
                content, _ = chunk_result
                response = rag.extract_direct_answer(q, content)
                results[q] = response or ""
            else:
                results[q] = ""
        except Exception:
            results[q] = ""
    await kos.disconnect()
    return results


def main():
    report_path = REPO_ROOT / "backend" / "validation_report.json"
    if not report_path.exists():
        print(f"❌ Отчёт не найден: {report_path}")
        return 1

    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    threshold = 0.9
    low_coherence = [
        r for r in data.get("results", [])
        if (m := r.get("metrics")) and m.get("coherence", 1) < threshold
    ]

    print(f"📊 Анализ coherence (отчёт: {report_path.name})")
    print(f"   Средний coherence: {data.get('avg_metrics', {}).get('coherence', 0):.1%}")
    print(f"   Запросов с coherence < {threshold:.0%}: {len(low_coherence)}")
    print("=" * 60)

    if not low_coherence:
        print("✅ Все запросы имеют coherence >= 90%")
        return 0

    # Получаем реальные ответы
    print("\n🔍 Загрузка ответов RAG для проблемных запросов...")
    responses = asyncio.run(fetch_responses_for_queries(low_coherence))

    for item in low_coherence:
        q = item["query"]
        coh = item["metrics"].get("coherence", 0)
        resp = responses.get(q, "")
        score, breakdown = _coherence_heuristic(resp)

        print(f"\n📌 '{q}'")
        print(f"   Coherence: {coh:.2f}")
        print(f"   Ответ ({len(resp)} символов): {resp[:120]}...")
        print(f"   Breakdown: base={breakdown['base']} punct={breakdown['punct']} long={breakdown['long']} no_spaces={breakdown['no_spaces']}")

        if coh < 0.8:
            if len(resp) < 50:
                print(f"   ⚠️ Причина: короткий ответ ({len(resp)} символов)")
            if "." not in resp and "!" not in resp and "?" not in resp:
                print(f"   ⚠️ Причина: нет точки в конце предложения")
            if len(resp) >= 10 and len(resp) < 30:
                print(f"   💡 Совет: extract_direct_answer обрезает — добавить точку при truncate")

    # Сохраняем
    out_path = REPO_ROOT / "coherence_issues_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "threshold": threshold,
            "low_coherence_count": len(low_coherence),
            "queries": [
                {
                    "query": r["query"],
                    "coherence": r["metrics"].get("coherence"),
                    "response": responses.get(r["query"], ""),
                    "response_len": len(responses.get(r["query"], "")),
                }
                for r in low_coherence
            ],
        }, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Сохранено: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
