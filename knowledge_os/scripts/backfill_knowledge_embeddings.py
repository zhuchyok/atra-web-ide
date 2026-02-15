#!/usr/bin/env python3
"""
Дозапись embedding для узлов knowledge_nodes без него (план «умнее быстрее» §4.1).

Nightly_learner и другие оркестраторы могут создавать узлы без embedding;
без embedding узлы не попадают в векторный RAG (WHERE embedding IS NOT NULL).
Скрипт находит такие узлы и заполняет embedding через get_embedding (Ollama, тот же
источник, что и для RAG в semantic_cache).

Запуск из корня репо или из knowledge_os:
  cd knowledge_os && python scripts/backfill_knowledge_embeddings.py [--limit N]
  или: python knowledge_os/scripts/backfill_knowledge_embeddings.py --limit 50

Рекомендуемый timeout запуска из IDE/CI: ≥ 5 мин при большом количестве узлов.
"""
import argparse
import asyncio
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _setup_path():
    """Добавить knowledge_os в path для импорта app.semantic_cache."""
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo not in sys.path:
        sys.path.insert(0, repo)
    app_dir = os.path.join(repo, "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)


async def run(limit: int = 100) -> int:
    """Найти узлы без embedding, вычислить и записать. Возвращает количество обновлённых."""
    _setup_path()
    try:
        import asyncpg
        from app.semantic_cache import get_embedding
    except ImportError as e:
        logger.error("Требуются asyncpg и app.semantic_cache (запуск из knowledge_os или с путём): %s", e)
        return 0

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.warning("DATABASE_URL не задан, дозапись пропущена")
        return 0

    conn = await asyncpg.connect(db_url)
    try:
        rows = await conn.fetch(
            """
            SELECT id, content
            FROM knowledge_nodes
            WHERE embedding IS NULL
              AND content IS NOT NULL
              AND trim(content) != ''
            ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
            LIMIT $1
            """,
            limit,
        )
        if not rows:
            logger.info("Узлов без embedding не найдено")
            return 0
        logger.info("Найдено узлов без embedding: %s, обрабатываем до %s", len(rows), limit)
        updated = 0
        for i, row in enumerate(rows):
            node_id = row["id"]
            content = (row["content"] or "").strip()
            if not content:
                continue
            text = content[:8000]
            try:
                embedding = await get_embedding(text)
                if embedding is not None:
                    await conn.execute(
                        "UPDATE knowledge_nodes SET embedding = $1::vector WHERE id = $2",
                        str(embedding),
                        node_id,
                    )
                    updated += 1
                    if (updated % 10) == 0:
                        logger.info("Обновлено %s/%s узлов", updated, len(rows))
            except Exception as e:
                logger.warning("Узел %s: %s", node_id, e)
        logger.info("Дозапись завершена: обновлено %s из %s узлов", updated, len(rows))
        return updated
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="Дозапись embedding для knowledge_nodes без него (§4.1)")
    parser.add_argument("--limit", type=int, default=100, help="Максимум узлов за один запуск (по умолчанию 100)")
    args = parser.parse_args()
    n = asyncio.run(run(limit=args.limit))
    return 0 if n >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
