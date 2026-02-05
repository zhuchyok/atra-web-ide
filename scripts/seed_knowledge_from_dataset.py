#!/usr/bin/env python3
"""
Загрузка базы знаний из data/validation_queries.json: для каждого запроса
добавляется узел с текстом «Вопрос: ... Ответ: ...» и эмбеддингом этого текста,
чтобы RAG находил релевантный контекст по запросу.

Запуск: python3 scripts/seed_knowledge_from_dataset.py
"""
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

DATASET = REPO_ROOT / "data" / "validation_queries.json"


async def main():
    if not DATASET.exists():
        print(f"❌ Датасет не найден: {DATASET}")
        return 1
    with open(DATASET, "r", encoding="utf-8") as f:
        data = json.load(f)
    queries = data.get("queries", data) if isinstance(data, dict) else data
    if not queries:
        print("Нет запросов в датасете.")
        return 0

    try:
        import asyncpg
        import httpx
        from app.config import get_settings
    except ImportError as e:
        print(f"Import error: {e}")
        return 1

    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)

    print("📦 Эмбеддинги через Ollama nomic-embed-text (768-dim)...")
    print("   Контент узлов: «Вопрос: ... Ответ: ...» для лучшего retrieval.\n")

    ollama_url = (getattr(settings, "ollama_url", None) or "http://localhost:11434").rstrip("/")
    model = getattr(settings, "ollama_embed_model", "nomic-embed-text")
    added = 0
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, item in enumerate(queries):
            q = item.get("query") if isinstance(item, dict) else None
            ref = item.get("reference") if isinstance(item, dict) else None
            if not q or not ref:
                continue
            content = f"Вопрос: {q}\nОтвет: {ref}"
            try:
                r = await client.post(
                    f"{ollama_url}/api/embeddings",
                    json={"model": model, "prompt": content[:8000]},
                )
                if r.status_code != 200:
                    print(f"⚠️ [{i+1}] {q[:40]}... Ollama {r.status_code}")
                    continue
                emb = r.json().get("embedding", [])
                if len(emb) != 768:
                    print(f"⚠️ [{i+1}] {q[:40]}... размерность {len(emb)} != 768")
                    continue
                await conn.execute(
                    """
                    INSERT INTO knowledge_nodes (content, embedding, metadata, confidence_score)
                    VALUES ($1, $2::vector, $3, 0.95)
                    """,
                    content,
                    str(emb),
                    json.dumps({"query": q, "source": "seed_dataset", "id": item.get("id", "")}),
                )
                added += 1
                if (added % 20) == 0:
                    print(f"   Добавлено {added} узлов...")
            except Exception as e:
                print(f"❌ [{i+1}] {q[:40]}... {e}")

    await conn.close()
    print(f"\n🎉 В базу знаний добавлено {added} узлов из {len(queries)} запросов датасета.")
    print("   Запустите пайплайн: ./scripts/run_quality_pipeline.sh")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
