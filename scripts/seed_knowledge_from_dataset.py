#!/usr/bin/env python3
"""
Загрузка базы знаний из data/validation_queries.json: для каждого запроса
добавляется узел с текстом «Вопрос: ... Ответ: ...» и эмбеддингом этого текста,
чтобы RAG находил релевантный контекст по запросу.

Эмбеддинги: hands Ollama (nomic) на :11437 — тот же URL, что LIVE RAG.
Не использовать brain :11434 (там нет nomic).

Запуск:
  LIVE_OLLAMA_URL=http://127.0.0.1:11437 python3 scripts/seed_knowledge_from_dataset.py
  python3 scripts/seed_knowledge_from_dataset.py --limit 5
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

DATASET = REPO_ROOT / "data" / "validation_queries.json"


def _embed_ollama_url() -> str:
    """LIVE_OLLAMA_URL → OLLAMA_EMBED_URL → hands :11437 (never brain :11434)."""
    return (
        (os.environ.get("LIVE_OLLAMA_URL") or "").strip()
        or (os.environ.get("OLLAMA_EMBED_URL") or "").strip()
        or "http://127.0.0.1:11437"
    ).rstrip("/").replace("/api/embeddings", "").replace("/api/embed", "")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Seed validation Q/A into knowledge_nodes")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Seed only first N queries (0=all). Matches RAG_LIVE_LIMIT smoke.",
    )
    parser.add_argument(
        "--dataset",
        default=str(DATASET),
        help="Path to validation_queries.json",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.is_absolute():
        dataset_path = REPO_ROOT / dataset_path
    if not dataset_path.exists():
        print(f"❌ Датасет не найден: {dataset_path}")
        return 1
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    queries = data.get("queries", data) if isinstance(data, dict) else data
    if not queries:
        print("Нет запросов в датасете.")
        return 0
    if args.limit and args.limit > 0:
        queries = queries[: args.limit]
        print(f"Seeding first {len(queries)} queries (--limit {args.limit})")

    try:
        import asyncpg
        import httpx
        from app.config import get_settings
    except ImportError as e:
        print(f"Import error: {e}")
        return 1

    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)

    ollama_url = _embed_ollama_url()
    model = getattr(settings, "ollama_embed_model", None) or os.environ.get(
        "OLLAMA_EMBED_MODEL", "nomic-embed-text"
    )
    print(f"📦 Эмбеддинги через {ollama_url} model={model} (ожидаем 768-dim)...")
    print("   Контент узлов: «Вопрос: ... Ответ: ...» для лучшего retrieval.\n")

    added = 0
    updated = 0
    skipped = 0
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, item in enumerate(queries):
            q = item.get("query") if isinstance(item, dict) else None
            ref = item.get("reference") if isinstance(item, dict) else None
            if not q or not ref:
                skipped += 1
                continue
            content = f"Вопрос: {q}\nОтвет: {ref}"
            qid = (item.get("id") if isinstance(item, dict) else None) or ""
            try:
                existing = await conn.fetchrow(
                    """
                    SELECT id, content FROM knowledge_nodes
                    WHERE COALESCE(metadata->>'source', '') = 'seed_dataset'
                      AND (
                        COALESCE(metadata->>'query', '') = $1
                        OR ($2 <> '' AND COALESCE(metadata->>'id', '') = $2)
                      )
                    LIMIT 1
                    """,
                    q,
                    str(qid),
                )
                if existing and (existing["content"] or "") == content:
                    skipped += 1
                    continue

                r = await client.post(
                    f"{ollama_url}/api/embeddings",
                    json={"model": model, "prompt": content[:8000]},
                )
                if r.status_code != 200:
                    print(f"⚠️ [{i+1}] {q[:40]}... Ollama {r.status_code} @ {ollama_url}")
                    continue
                emb = r.json().get("embedding", [])
                if len(emb) != 768:
                    print(f"⚠️ [{i+1}] {q[:40]}... размерность {len(emb)} != 768")
                    continue

                meta = json.dumps(
                    {"query": q, "source": "seed_dataset", "id": qid},
                    ensure_ascii=False,
                )
                if existing:
                    await conn.execute(
                        """
                        UPDATE knowledge_nodes
                        SET content = $1,
                            embedding = $2::vector,
                            metadata = $3::jsonb,
                            confidence_score = 0.95
                        WHERE id = $4
                        """,
                        content,
                        str(emb),
                        meta,
                        existing["id"],
                    )
                    updated += 1
                else:
                    await conn.execute(
                        """
                        INSERT INTO knowledge_nodes (content, embedding, metadata, confidence_score)
                        VALUES ($1, $2::vector, $3::jsonb, 0.95)
                        """,
                        content,
                        str(emb),
                        meta,
                    )
                    added += 1
                if ((added + updated) % 20) == 0 and (added + updated) > 0:
                    print(f"   upserted {added + updated} узлов...")
            except Exception as e:
                print(f"❌ [{i+1}] {q[:40]}... {e}")

    await conn.close()
    print(
        f"\n🎉 seed_dataset: added={added} updated={updated} skipped={skipped} "
        f"(from {len(queries)} queries)."
    )
    print("   Re-run: LIVE_RAG_QUALITY=1 ./scripts/run_live_rag_quality.sh")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
