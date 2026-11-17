#!/usr/bin/env python3
"""
Бенчмарк latency для RAG (Фаза 4.1).
Цель: P95 < 300ms. Измеряет: query_expansion, embedding, vector_search, extract_answer.
Учитывает: Ollama (embeddings), MLX (LLM fallback в Ask).
"""
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import List, Dict

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))


def _check_services() -> Dict[str, bool]:
    """Проверка доступности Ollama и MLX."""
    import os
    result = {"ollama": False, "mlx": False}
    try:
        import httpx
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        mlx_url = os.getenv("MLX_API_URL", "http://localhost:11435")
        with httpx.Client(timeout=2.0) as c:
            r = c.get(f"{ollama_url}/api/tags")
            result["ollama"] = r.status_code == 200
        with httpx.Client(timeout=2.0) as c:
            r = c.get(f"{mlx_url}/health")
            result["mlx"] = r.status_code == 200 and r.json().get("status") in ("healthy", "degraded")
    except Exception:
        pass
    return result


async def measure_rag_latency(queries: List[str], samples: int = 3) -> List[Dict]:
    """Измеряет latency по этапам для каждого запроса."""
    try:
        from app.services.knowledge_os import KnowledgeOSClient
        from app.services.rag_light import RAGLightService
        from app.services.latency_tracer import latency_tracer
    except ImportError as e:
        print(f"Import error: {e}")
        return []

    kos = KnowledgeOSClient()
    await kos.connect()
    rag = RAGLightService(knowledge_os=kos)

    results = []
    for q in queries:
        for sample in range(samples):
            latency_tracer.start_trace(f"q_{len(results)}")
            t0 = time.perf_counter()

            with latency_tracer.measure("query_expansion"):
                search_q = rag._expand_query_for_search(q)

            with latency_tracer.measure("embedding"):
                embedding = await rag._get_embedding_optimized(search_q)

            if not embedding:
                results.append({"query": q[:40], "total_ms": -1, "error": "no_embedding", "spans": []})
                continue

            with latency_tracer.measure("vector_search"):
                chunk_result = await rag.search_one_chunk(q, limit=1)

            if not chunk_result:
                results.append({"query": q[:40], "total_ms": (time.perf_counter() - t0) * 1000, "error": "no_chunk", "spans": latency_tracer.get_trace_summary().get("spans", [])})
                continue

            content, _ = chunk_result
            with latency_tracer.measure("extract_answer"):
                _ = rag.extract_direct_answer(q, content)

            total_ms = (time.perf_counter() - t0) * 1000
            summary = latency_tracer.get_trace_summary()
            results.append({
                "query": q[:40],
                "total_ms": total_ms,
                "spans": summary.get("spans", []),
                "bottlenecks": summary.get("bottlenecks", []),
                "error": None,
            })

    await kos.disconnect()
    return results


def _extract_answer_smoke(query: str, chunk: str) -> str:
    """Minimal Q/A extract for offline smoke when RAGLightService is unavailable."""
    for marker in ("\nОтвет:", "\nAnswer:", "Ответ:", "Answer:"):
        idx = chunk.find(marker)
        if idx >= 0:
            return chunk[idx + len(marker) :].strip()[:400]
    return chunk.strip()[:400]


def measure_local_extract_smoke(queries: List[str], samples: int = 5) -> List[Dict]:
    """Offline latency smoke: extract_direct_answer only (no Ollama/DB)."""
    extract_fn = _extract_answer_smoke
    try:
        from app.services.rag_light import RAGLightService

        rag = RAGLightService(
            knowledge_os=None,
            max_response_length=400,
            config={
                "query_rewriter_enabled": False,
                "query_expansion_enabled": False,
                "reranking_enabled": False,
            },
        )
        extract_fn = rag.extract_direct_answer
    except ImportError as e:
        print(f"   RAGLightService unavailable ({e}); using inline extract smoke")

    fixtures = {
        "сколько стоит подписка": "Стоимость подписки составляет 999 рублей в месяц.",
        "как создать аккаунт": "Для создания аккаунта перейдите на страницу регистрации.",
        "контакты поддержки": "Email: support@atra.ai, Telegram: @atra_support.",
        "документация API": "Документация API доступна по адресу /docs (Swagger UI).",
        "как настроить Victoria": "Victoria настраивается через VICTORIA_URL (порт 8010).",
    }
    results = []
    for q in queries:
        ref = fixtures.get(q, f"Ответ на запрос: {q}")
        chunk = f"Вопрос: {q}\nОтвет: {ref}"
        for _ in range(samples):
            t0 = time.perf_counter()
            _ = extract_fn(q, chunk)
            total_ms = (time.perf_counter() - t0) * 1000
            results.append(
                {
                    "query": q[:40],
                    "total_ms": total_ms,
                    "spans": [{"name": "extract_answer", "duration_ms": total_ms}],
                    "bottlenecks": [],
                    "error": None,
                }
            )
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RAG latency benchmark")
    parser.add_argument("--no-fail", action="store_true", help="Не выходить с кодом 1 при ошибках (для CI)")
    parser.add_argument(
        "--mode",
        choices=("live", "local_smoke"),
        default="live",
        help="live=full RAG path; local_smoke=offline extract_direct_answer only",
    )
    args = parser.parse_args()

    # Тестовые запросы из validation set
    queries = [
        "сколько стоит подписка",
        "как создать аккаунт",
        "контакты поддержки",
        "документация API",
        "как настроить Victoria",
    ]

    print("⚡ Бенчмарк latency RAG")
    print("=" * 50)
    print(f"Mode: {args.mode}")

    svc = _check_services()
    print(f"   Ollama (embeddings): {'✅' if svc['ollama'] else '❌'}")
    print(f"   MLX (LLM fallback):  {'✅' if svc['mlx'] else '❌'}")
    if args.mode == "live" and not svc["ollama"]:
        print("   ⚠️  Ollama недоступна — будет fallback на sentence-transformers (медленно)")
        print("      Запустите: ollama serve && ollama pull nomic-embed-text")
    print()

    if args.mode == "local_smoke":
        results = measure_local_extract_smoke(queries, samples=5)
    else:
        results = asyncio.run(measure_rag_latency(queries, samples=2))

    valid = [r for r in results if r.get("total_ms", 0) >= 0]
    if not valid:
        print("❌ Нет успешных измерений")
        return 0 if args.no_fail else 1

    times = sorted([r["total_ms"] for r in valid])
    n = len(times)
    p50 = times[int(n * 0.5)] if n else 0
    p95 = times[int(n * 0.95)] if n > 1 else times[-1]
    p99 = times[int(n * 0.99)] if n > 1 else times[-1]
    avg = sum(times) / n

    print(f"\n📊 Перцентили (n={n} запросов):")
    print(f"   P50:  {p50:.0f} ms")
    # local_smoke is not a live P95 SLA claim; keep a generous sanity ceiling
    sla_ms = 300 if args.mode == "live" else 50
    print(f"   P95:  {p95:.0f} ms  {'✅' if p95 < sla_ms else '❌'} (цель < {sla_ms}ms)")
    print(f"   P99:  {p99:.0f} ms")
    print(f"   Avg:  {avg:.0f} ms")

    # Узкие места
    span_totals = {}
    for r in valid:
        for s in r.get("spans", []):
            name = s.get("name", "?")
            span_totals[name] = span_totals.get(name, 0) + s.get("duration_ms", 0)

    if span_totals:
        total_span = sum(span_totals.values())
        print("\n🔍 Время по этапам:")
        for name, ms in sorted(span_totals.items(), key=lambda x: -x[1]):
            pct = (ms / total_span * 100) if total_span else 0
            print(f"   {name}: {ms/n:.0f} ms avg ({pct:.0f}%)")

    # Сохраняем
    out = REPO_ROOT / "latency_benchmark.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "mode": args.mode,
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
            "avg_ms": avg,
            "n_requests": n,
            "services": svc,
            "results": results,
            "span_totals": span_totals,
            "note": (
                "Offline local_smoke: extract_direct_answer only; not live RAG latency."
                if args.mode == "local_smoke"
                else "Live RAG latency path."
            ),
        }, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Сохранено: {out}")

    if p95 >= sla_ms and not args.no_fail:
        print(f"❌ P95 SLA failed (>= {sla_ms}ms)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
