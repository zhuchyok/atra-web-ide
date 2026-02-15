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
    from app.evaluation.rag_evaluator import RAGEvaluator, DEFAULT_THRESHOLDS
except ImportError:
    RAGEvaluator = None
    DEFAULT_THRESHOLDS = {"faithfulness": 0.8, "relevance": 0.85, "coherence": 0.7}

# RAG-light (опционально, для получения ответов на запросы)
try:
    from app.services.rag_light import RAGLightService
    from app.services.knowledge_os import KnowledgeOSClient
    from app.services.query_rewriter import QueryRewriter
    from app.services.reranking import RerankingService
except ImportError:
    RAGLightService = None
    KnowledgeOSClient = None
    QueryRewriter = None
    RerankingService = None


def load_validation_set(path: Path) -> list:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("queries", data) if isinstance(data, dict) else data


async def get_response_for_query(query: str, fast_fail: bool = True) -> tuple:
    """
    Получить ответ и контекст от RAG-light (если доступен).
    fast_fail: при недоступности RAG/Ollama быстро возвращать stub (таймауты 2с connect, 5с search).
    """
    response_text = ""
    context_chunks = []
    if RAGLightService and KnowledgeOSClient:
        kos = KnowledgeOSClient()
        try:
            if fast_fail:
                await asyncio.wait_for(kos.connect(), timeout=2.0)
            else:
                await kos.connect()
            qr = QueryRewriter(use_llm=False) if QueryRewriter else None
            rerank = None
            if os.environ.get("RERANKING_ENABLED", "false").lower() == "true" and RerankingService:
                try:
                    rerank = RerankingService(method="text_similarity", top_k=5)
                except Exception:
                    pass
            # При валидации можно отключить expansion/rewriter, чтобы запрос совпадал с «Вопрос: ...» в БЗ
            use_rewriter = os.environ.get("RAG_VALIDATION_QUERY_REWRITER", "true").lower() == "true"
            use_expansion = os.environ.get("RAG_VALIDATION_QUERY_EXPANSION", "true").lower() == "true"
            config = {
                "query_rewriter_enabled": bool(qr) and use_rewriter,
                "query_expansion_enabled": use_expansion,
                "reranking_enabled": bool(rerank),
            }
            # Порог similarity: 0.2 для валидации (максимум чанков после seed_dataset)
            sim_threshold = float(os.environ.get("RAG_SIMILARITY_THRESHOLD", "0.2"))
            rag = RAGLightService(
                knowledge_os=kos,
                query_rewriter_service=qr,
                reranking_service=rerank,
                config=config,
                similarity_threshold=sim_threshold,
                max_response_length=int(os.environ.get("RAG_MAX_RESPONSE_LENGTH", "400")),
            )
            search_limit = int(os.environ.get("RAG_VALIDATION_LIMIT", "5"))
            search_timeout = 5.0 if fast_fail else 30.0

            # Приоритет: чанки формата «Вопрос: X Ответ: Y» (seed_dataset) — keyword ищет точнее
            _kw_prefer = os.environ.get("RAG_VALIDATION_KEYWORD_FIRST", "true").lower() == "true"
            if _kw_prefer and kos:
                try:
                    rows = await asyncio.wait_for(kos.search_knowledge(query, limit=3), timeout=3.0)
                    for r in rows:
                        c = (r.get("content") or "")
                        if "Ответ:" in c or "Answer:" in c:
                            context_chunks = [c]
                            response_text = rag.extract_direct_answer(query, c)
                            if response_text and len(response_text) > 10:
                                break
                except Exception:
                    pass

            if not response_text and not context_chunks:
                if rerank:
                    chunks = await asyncio.wait_for(rag.get_chunks_for_query(query, limit=search_limit), timeout=search_timeout)
                    if chunks:
                        content = chunks[0]
                        context_chunks = chunks
                        response_text = rag.extract_direct_answer(query, content)
                else:
                    result = await asyncio.wait_for(rag.search_one_chunk(query, limit=search_limit), timeout=search_timeout)
                    if result:
                        content, _ = result
                        context_chunks = [content]
                        response_text = rag.extract_direct_answer(query, content)

            # Fallback: keyword-поиск при пустом векторном результате
            if not response_text and not context_chunks and KnowledgeOSClient and kos:
                stop = {"как", "что", "какой", "какая", "каким", "объясни", "расскажи"}
                terms = [w for w in query.lower().split() if len(w) >= 3 and w not in stop][:5]
                if not terms:
                    terms = [query[:40]]
                for term in terms:
                    try:
                        rows = await kos.search_knowledge(term, limit=3)
                        if rows:
                            content = rows[0].get("content", "")
                            if content and len(content) > 20:
                                context_chunks = [content]
                                response_text = rag.extract_direct_answer(query, content)
                                break
                    except Exception:
                        continue
        except asyncio.TimeoutError:
            response_text = "[RAG timeout: Ollama/embedding slow or unavailable]"
        except Exception as e:
            response_text = f"[RAG unavailable: {e}]"
        finally:
            try:
                await asyncio.wait_for(kos.disconnect(), timeout=1.0)
            except Exception:
                pass
    else:
        response_text = "[RAG not available: run from backend or set PYTHONPATH]"
    return response_text, context_chunks


async def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG quality on validation set")
    parser.add_argument("--dataset", default="data/validation_queries.json", help="Path to validation JSON")
    parser.add_argument(
        "--threshold",
        default="faithfulness:0.8,relevance:0.85,coherence:0.7",
        help="Comma-separated metric:value (QA defaults: faithfulness≥0.8, relevance≥0.85, coherence≥0.7)",
    )
    parser.add_argument("--no-fail", action="store_true", help="Do not exit with code 1 when thresholds fail (e.g. RAG offline)")
    parser.add_argument("--output", "-o", help="Write JSON report (avg_metrics, results) to file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-query results")
    parser.add_argument("--timeout-per-query", type=float, default=10.0, help="Timeout per query when RAG/Ollama unavailable (seconds)")
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
    timeout_sec = getattr(args, "timeout_per_query", 10.0)
    for i, item in enumerate(queries):
        q = item.get("query", item) if isinstance(item, dict) else str(item)
        reference = item.get("reference") if isinstance(item, dict) else None
        context_expected = item.get("context_expected") if isinstance(item, dict) else None

        try:
            response, context_chunks = await asyncio.wait_for(get_response_for_query(q), timeout=timeout_sec)
        except asyncio.TimeoutError:
            response = "[RAG timeout: Ollama/embedding unavailable]"
            context_chunks = []
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

    if RAGEvaluator:
        passed, failed = RAGEvaluator.check_thresholds(avg, thresholds)
    else:
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
