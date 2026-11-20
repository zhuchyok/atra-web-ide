#!/usr/bin/env python3
"""
Фаза 4: оценка качества RAG на validation set.

Использование:
  # PR/CI offline smoke (no Ollama/seeded KB required):
  python scripts/evaluate_rag_quality.py --mode reference_smoke --dataset data/validation_queries.json

  # LIVE retrieval (Mac Studio / host with Ollama+Postgres). Fail-closed if services missing:
  LIVE_RAG_QUALITY=1 OLLAMA_URL=http://127.0.0.1:11437 \\
    python scripts/evaluate_rag_quality.py --mode live --dataset data/validation_queries.json \\
    --output logs/rag_quality_live.json

  # Same via host entrypoint:
  ./scripts/run_live_rag_quality.sh

Пороги: при нарушении любого порога скрипт завершается с ненулевым кодом (для CI).
Live mode never green-passes on missing Ollama/DB or stub "[RAG unavailable]" answers.
"""

import argparse
import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
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


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _ollama_base_url() -> str:
    """Hands nomic first — same contract as seed_knowledge_from_dataset / run_live_rag_quality.sh.

    Prefer LIVE_OLLAMA_URL / OLLAMA_EMBED_URL so a brain-only OLLAMA_BASE_URL from .env
    cannot hijack embeds (brain :11434 has victoria-qwen38 only; nomic lives on :11437).
    """
    return (
        os.environ.get("LIVE_OLLAMA_URL")
        or os.environ.get("OLLAMA_EMBED_URL")
        or os.environ.get("OLLAMA_URL")
        or os.environ.get("OLLAMA_BASE_URL")
        or "http://127.0.0.1:11437"
    ).rstrip("/")


async def _preflight_live_services() -> dict:
    """
    Fail-closed checks for live RAG. Returns probe metadata or exits 1.
    Never returns success when Ollama or Postgres is unreachable.
    """
    meta = {"ollama_url": _ollama_base_url(), "ollama_ok": False, "db_ok": False, "kb_rows": None}
    ollama_url = meta["ollama_url"]
    try:
        req = urllib.request.Request(f"{ollama_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            meta["ollama_ok"] = int(getattr(resp, "status", 200) or 200) == 200
            if meta["ollama_ok"]:
                try:
                    payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
                    names = [m.get("name", "") for m in payload.get("models", [])]
                    meta["ollama_models"] = names[:12]
                    meta["has_nomic"] = any("nomic-embed" in n for n in names)
                except Exception:
                    meta["ollama_models"] = []
                    meta["has_nomic"] = False
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(
            f"LIVE RAG preflight FAIL: Ollama unreachable at {ollama_url}: {e}",
            file=sys.stderr,
        )
        print(
            "Hint: start Ollama. On Mac Studio hands (nomic) use "
            "OLLAMA_URL=http://127.0.0.1:11437 (brain 11434 has no nomic).",
            file=sys.stderr,
        )
        raise RuntimeError(f"ollama_unreachable:{ollama_url}") from e

    if not meta["ollama_ok"]:
        print(f"LIVE RAG preflight FAIL: Ollama bad status at {ollama_url}", file=sys.stderr)
        raise RuntimeError(f"ollama_bad_status:{ollama_url}")

    if KnowledgeOSClient is None:
        print(
            "LIVE RAG preflight FAIL: KnowledgeOSClient import failed "
            "(run with PYTHONPATH=backend:.).",
            file=sys.stderr,
        )
        raise RuntimeError("knowledge_os_import_failed")

    kos = KnowledgeOSClient()
    try:
        await asyncio.wait_for(kos.connect(), timeout=5.0)
        rows = await asyncio.wait_for(kos.search_knowledge("подписка", limit=1), timeout=8.0)
        meta["db_ok"] = True
        meta["kb_rows"] = len(rows or [])
    except Exception as e:
        print(f"LIVE RAG preflight FAIL: Postgres/Knowledge OS unreachable: {e}", file=sys.stderr)
        print(
            "Hint: set DATABASE_URL and ensure knowledge_postgres is up "
            "(e.g. postgresql://admin:***@localhost:5432/knowledge_os).",
            file=sys.stderr,
        )
        raise RuntimeError(f"postgres_unreachable:{e}") from e
    finally:
        try:
            await asyncio.wait_for(kos.disconnect(), timeout=2.0)
        except Exception:
            pass

    require_nomic = _env_truthy("LIVE_RAG_REQUIRE_NOMIC") or _env_truthy("LIVE_RAG_QUALITY")
    if meta.get("has_nomic") is False:
        msg = (
            "nomic-embed-text not listed on "
            f"{ollama_url}; vector path would degrade (MiniLM 384 vs KB 768)."
        )
        if require_nomic and not _env_truthy("LIVE_RAG_ALLOW_NO_NOMIC"):
            print(f"LIVE RAG preflight FAIL: {msg}", file=sys.stderr)
            print(
                "Hint: set LIVE_OLLAMA_URL=http://127.0.0.1:11437 (hands) "
                "or LIVE_RAG_ALLOW_NO_NOMIC=1 for keyword-only (not real embeds).",
                file=sys.stderr,
            )
            raise RuntimeError(f"nomic_missing:{ollama_url}")
        print(f"LIVE RAG preflight WARN: {msg}", file=sys.stderr)

    print(
        f"LIVE RAG preflight OK: ollama={ollama_url} "
        f"nomic={meta.get('has_nomic')} db=ok kb_probe_rows={meta.get('kb_rows')}"
    )
    return meta


def _is_stub_response(response: str) -> bool:
    text = (response or "").strip()
    if not text:
        return True
    stubs = (
        "[RAG unavailable",
        "[RAG timeout",
        "[RAG not available",
    )
    return any(text.startswith(s) for s in stubs)


def _is_seed_qa_chunk(content: str, query: str) -> bool:
    """
    True only for seed_dataset-style «Вопрос: <query>\\nОтвет: ...» chunks.

    Free-form docs that merely contain «Ответ:» / FAQ sections (long_term_memory,
    AutoGen FAQs, etc.) must not win keyword-first — they yield faithfulness≈1
    and relevance=0 against the validation reference.
    """
    if not content or not query:
        return False
    c = content.strip()
    q = query.strip().lower()
    has_ru = "Вопрос:" in c and "Ответ:" in c
    has_en = "Question:" in c and "Answer:" in c
    if not (has_ru or has_en):
        return False
    # Prefer match on the question side (before answer marker), not answer body.
    for marker in ("\nОтвет:", "\nAnswer:", "Ответ:", "Answer:"):
        idx = c.find(marker)
        if idx >= 0:
            return q in c[:idx].lower()
    return False


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

            # Приоритет: только seed «Вопрос: <query> Ответ: Y» — не любой чанк с «Ответ:»
            _kw_prefer = os.environ.get("RAG_VALIDATION_KEYWORD_FIRST", "true").lower() == "true"
            if _kw_prefer and kos:
                try:
                    rows = await asyncio.wait_for(kos.search_knowledge(query, limit=5), timeout=3.0)
                    for r in rows:
                        c = (r.get("content") or "")
                        if not _is_seed_qa_chunk(c, query):
                            continue
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


def _reference_smoke_pair(query: str, reference: str) -> tuple:
    """
    Offline smoke: build Q/A chunk and extract answer locally (no Ollama/DB).
    Metrics are real RAGEvaluator scores over extract_direct_answer output — not live retrieval.
    """
    chunk = f"Вопрос: {query}\nОтвет: {reference}"
    response = reference
    if RAGLightService is not None:
        try:
            rag = RAGLightService(
                knowledge_os=None,
                max_response_length=400,
                config={
                    "query_rewriter_enabled": False,
                    "query_expansion_enabled": False,
                    "reranking_enabled": False,
                },
            )
            extracted = rag.extract_direct_answer(query, chunk)
            if extracted and len(extracted.strip()) >= 10:
                response = extracted
        except Exception:
            response = reference
    return response, [chunk]


async def main():
    parser = argparse.ArgumentParser(
        description="Evaluate RAG quality on validation set",
        epilog=(
            "LIVE one-liner (Mac Studio): "
            "LIVE_RAG_QUALITY=1 OLLAMA_URL=http://127.0.0.1:11437 "
            "./scripts/run_live_rag_quality.sh"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dataset", default="data/validation_queries.json", help="Path to validation JSON")
    parser.add_argument(
        "--threshold",
        default="faithfulness:0.8,relevance:0.85,coherence:0.7",
        help="Comma-separated metric:value (QA defaults: faithfulness≥0.8, relevance≥0.85, coherence≥0.7)",
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Do not exit 1 when thresholds fail (forbidden when LIVE_RAG_QUALITY=1 / --require-live)",
    )
    parser.add_argument("--output", "-o", help="Write JSON report (avg_metrics, results) to file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-query results")
    parser.add_argument("--timeout-per-query", type=float, default=10.0, help="Timeout per query when RAG/Ollama unavailable (seconds)")
    parser.add_argument(
        "--mode",
        choices=("live", "reference_smoke"),
        default="live",
        help="live=RAG retrieval (needs DB/Ollama); reference_smoke=offline extract+evaluator over dataset references",
    )
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="Force fail-closed live preflight (also implied by LIVE_RAG_QUALITY=1)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Evaluate only first N queries (0=all). Useful for host live smoke.",
    )
    args = parser.parse_args()

    path = REPO_ROOT / args.dataset
    if not path.exists():
        print(f"Dataset not found: {path}", file=sys.stderr)
        return 1

    queries = load_validation_set(path)
    if not queries:
        print("No queries in dataset.", file=sys.stderr)
        return 1
    if args.limit and args.limit > 0:
        queries = queries[: args.limit]
        print(f"Using first {len(queries)} queries (--limit {args.limit})")

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

    mode = args.mode
    live_gate = mode == "live" and (args.require_live or _env_truthy("LIVE_RAG_QUALITY"))
    # Default live (without LIVE_RAG_QUALITY) still preflights fail-closed: no silent green stubs.
    require_services = mode == "live"
    if args.no_fail and live_gate:
        print(
            "LIVE RAG refuse --no-fail under LIVE_RAG_QUALITY=1 / --require-live (fail-closed).",
            file=sys.stderr,
        )
        return 1

    preflight_meta = None
    if mode == "reference_smoke":
        print("Mode: reference_smoke (offline; not live RAG retrieval)")
    else:
        print("Mode: live (real RAG retrieval; fail-closed if Ollama/DB missing)")
        if require_services:
            try:
                preflight_meta = await _preflight_live_services()
            except RuntimeError as e:
                print(f"LIVE RAG aborted: {e}", file=sys.stderr)
                return 1
    results = []
    stub_count = 0
    timeout_sec = getattr(args, "timeout_per_query", 10.0)
    skipped_no_ref = 0
    for i, item in enumerate(queries):
        q = item.get("query", item) if isinstance(item, dict) else str(item)
        reference = item.get("reference") if isinstance(item, dict) else None
        context_expected = item.get("context_expected") if isinstance(item, dict) else None

        if mode == "reference_smoke":
            if not reference or not str(reference).strip():
                skipped_no_ref += 1
                continue
            response, context_chunks = _reference_smoke_pair(q, str(reference))
            context = context_chunks
        else:
            try:
                response, context_chunks = await asyncio.wait_for(
                    get_response_for_query(q, fast_fail=not live_gate),
                    timeout=timeout_sec,
                )
            except asyncio.TimeoutError:
                response = "[RAG timeout: Ollama/embedding unavailable]"
                context_chunks = []
            if _is_stub_response(response) or not context_chunks:
                stub_count += 1
            context = context_chunks or ([" ".join(context_expected)] if context_expected else [])

        metrics = await evaluator.evaluate_response(q, response, context, reference=reference)
        results.append({"query": q[:60], "metrics": metrics, "stub": _is_stub_response(response) if mode == "live" else False})

        if args.verbose:
            print(f"  [{i+1}] {q[:50]}... faithfulness={metrics.get('faithfulness', 0):.2f} relevance={metrics.get('relevance', 0):.2f}")

    # Aggregates
    n = len(results)
    if n < 1:
        print("No evaluable queries (reference_smoke requires reference fields).", file=sys.stderr)
        return 1
    if mode == "reference_smoke" and skipped_no_ref:
        print(f"Skipped {skipped_no_ref} items without reference", file=sys.stderr)

    if mode == "live" and stub_count > 0:
        # Fail-closed: any stub means retrieval did not actually run for that query.
        # Under LIVE_RAG_QUALITY / --require-live: refuse green even if averages look fine.
        # Always refuse if majority are stubs (would fake quality).
        stub_ratio = stub_count / float(n)
        print(
            f"LIVE RAG: stub/empty retrieval on {stub_count}/{n} queries "
            f"({stub_ratio:.0%})",
            file=sys.stderr,
        )
        if live_gate or stub_ratio >= 0.5:
            print(
                "LIVE RAG FAIL: refusing green pass on stub/empty live retrieval "
                "(fix Ollama embeddings / seeded KB).",
                file=sys.stderr,
            )
            if args.output:
                out_path = Path(args.output)
                if not out_path.is_absolute():
                    out_path = REPO_ROOT / args.output
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "timestamp": __import__("datetime").datetime.now().isoformat(),
                            "mode": "live",
                            "avg_metrics": {},
                            "total_queries": n,
                            "stub_count": stub_count,
                            "passed": False,
                            "skipped": False,
                            "preflight": preflight_meta,
                            "note": "Live retrieval stubs/empty contexts — fail-closed.",
                            "results": results,
                            "thresholds": thresholds,
                        },
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )
                print(f"\nReport written to {out_path}")
            return 1

    avg = {}
    for k in ["faithfulness", "relevance", "coherence"]:
        vals = [r["metrics"].get(k, 0) for r in results if r["metrics"]]
        avg[k] = sum(vals) / len(vals) if vals else 0.0

    print("\n--- RAG Quality Evaluation ---")
    print(f"Mode: {mode}")
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
        passed = len(failed) == 0

    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = REPO_ROOT / args.output
        report = {
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "mode": mode,
            "avg_metrics": avg,
            "total_queries": n,
            "results": results,
            "thresholds": thresholds,
            "passed": bool(passed) and len(failed) == 0,
            "skipped": False,
        }
        if mode == "reference_smoke":
            report["note"] = (
                "Offline reference_smoke: extract_direct_answer over dataset Q/A chunks; "
                "not live retrieval. Live RAG still requires seeded DB + Ollama."
            )
        else:
            report["note"] = (
                "LIVE retrieval against real Knowledge OS + Ollama embeddings path. "
                "Not CI reference_smoke."
            )
            report["stub_count"] = stub_count
            if preflight_meta is not None:
                report["preflight"] = preflight_meta
            if live_gate:
                report["live_gate"] = "LIVE_RAG_QUALITY"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nReport written to {out_path}")

    if failed:
        print("\nThresholds failed: " + ", ".join(failed), file=sys.stderr)
        return 0 if (args.no_fail and not live_gate) else 1
    print("\nAll thresholds passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
