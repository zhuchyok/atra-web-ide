#!/usr/bin/env python3
"""
Фаза 4: оценка качества RAG на validation set.

Использование:
  python scripts/evaluate_rag_quality.py --dataset data/validation_queries.json
  python scripts/evaluate_rag_quality.py --dataset data/validation_queries.json --threshold faithfulness:0.8,relevance:0.85

Пороги: при нарушении любого порога скрипт завершается с ненулевым кодом (для CI).
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))

# Backend app
os.environ.setdefault("BACKEND_APP", "1")
try:
    from app.evaluation.rag_evaluator import RAGEvaluator
except ImportError:
    RAGEvaluator = None

# RAG-light (опционально, для получения ответов на запросы)
try:
    from app.services.rag_light import RAGLightService
    from app.services.knowledge_os import KnowledgeOSClient
except ImportError:
    RAGLightService = None
    KnowledgeOSClient = None


def load_validation_set(path: Path) -> list:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("queries", data) if isinstance(data, dict) else data


async def get_response_for_query(query: str) -> tuple:
    """Получить ответ и контекст от RAG-light (если доступен)."""
    response_text = ""
    context_chunks = []
    if RAGLightService and KnowledgeOSClient:
        kos = KnowledgeOSClient()
        try:
            await kos.connect()
            rag = RAGLightService(knowledge_os=kos)
            result = await rag.search_one_chunk(query, limit=3)
            if result:
                content, _ = result
                context_chunks = [content]
                response_text = rag.extract_direct_answer(query, content)
        except Exception as e:
            response_text = f"[RAG unavailable: {e}]"
        finally:
            await kos.disconnect()
    else:
        response_text = "[RAG not available: run from backend or set PYTHONPATH]"
    return response_text, context_chunks


async def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG quality on validation set")
    parser.add_argument("--dataset", default="data/validation_queries.json", help="Path to validation JSON")
    parser.add_argument("--threshold", default="faithfulness:0.8,relevance:0.85", help="Comma-separated metric:value")
    parser.add_argument("--no-fail", action="store_true", help="Do not exit with code 1 when thresholds fail (e.g. RAG offline)")
    parser.add_argument("--output", "-o", help="Write JSON report (avg_metrics, results) to file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-query results")
    args = parser.parse_args()

    path = REPO_ROOT / args.dataset
    if not path.exists():
        print(f"Dataset not found: {path}", file=sys.stderr)
        return 1

    queries = load_validation_set(path)
    if not queries:
        print("No queries in dataset.", file=sys.stderr)
        return 1

    thresholds = {}
    for part in args.threshold.split(","):
        part = part.strip()
        if ":" in part:
            k, v = part.split(":", 1)
            thresholds[k.strip()] = float(v.strip())

    evaluator = RAGEvaluator() if RAGEvaluator else None
    if not evaluator:
        print("RAGEvaluator not available.", file=sys.stderr)
        return 1

    results = []
    for i, item in enumerate(queries):
        q = item.get("query", item) if isinstance(item, dict) else str(item)
        reference = item.get("reference") if isinstance(item, dict) else None
        context_expected = item.get("context_expected") if isinstance(item, dict) else None

        response, context_chunks = await get_response_for_query(q)
        context = context_chunks or ([" ".join(context_expected)] if context_expected else [])

        metrics = await evaluator.evaluate_response(q, response, context, reference=reference)
        results.append({"query": q[:60], "metrics": metrics})

        if args.verbose:
            print(f"  [{i+1}] {q[:50]}... faithfulness={metrics.get('faithfulness', 0):.2f} relevance={metrics.get('relevance', 0):.2f}")

    # Aggregates
    n = len(results)
    avg = {}
    for k in ["faithfulness", "relevance", "coherence"]:
        vals = [r["metrics"].get(k, 0) for r in results if r["metrics"]]
        avg[k] = sum(vals) / len(vals) if vals else 0.0

    print("\n--- RAG Quality Evaluation ---")
    print(f"Queries: {n}")
    print(f"Average faithfulness: {avg.get('faithfulness', 0):.3f}")
    print(f"Average relevance:     {avg.get('relevance', 0):.3f}")
    print(f"Average coherence:     {avg.get('coherence', 0):.3f}")

    failed = []
    for name, th in thresholds.items():
        val = avg.get(name)
        if val is not None and val < th:
            failed.append(f"{name}={val:.3f} < {th}")

    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = REPO_ROOT / args.output
        report = {
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "avg_metrics": avg,
            "total_queries": n,
            "results": results,
            "thresholds": thresholds,
            "passed": len(failed) == 0,
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nReport written to {out_path}")

    if failed:
        print("\nThresholds failed: " + ", ".join(failed), file=sys.stderr)
        return 0 if args.no_fail else 1
    print("\nAll thresholds passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
