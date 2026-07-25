#!/usr/bin/env python3
"""
Дозапись embedding для RAG-eligible узлов без вектора.

Приоритет: mentorship / SOP / council / board / distilled / LTM.
Junk (venv, audit, discovery stubs) не трогаем.

  cd knowledge_os && python scripts/backfill_knowledge_embeddings.py [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _setup_path() -> None:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo not in sys.path:
        sys.path.insert(0, repo)
    app_dir = os.path.join(repo, "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    if os.path.exists("/app/knowledge_os"):
        sys.path.insert(0, "/app/knowledge_os")


async def run(limit: int = 100) -> int:
    _setup_path()
    try:
        from app.embedding_eligibility import backfill_eligible_embeddings
    except ImportError:
        from embedding_eligibility import backfill_eligible_embeddings

    if not os.getenv("DATABASE_URL"):
        logger.warning("DATABASE_URL не задан, дозапись пропущена")
        return 0

    stats = await backfill_eligible_embeddings(limit=limit)
    logger.info(
        "Дозапись завершена: updated=%s failed=%s candidates=%s",
        stats.get("updated"),
        stats.get("failed"),
        stats.get("candidates"),
    )
    return int(stats.get("updated") or 0)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Priority RAG embedding backfill for eligible knowledge_nodes"
    )
    parser.add_argument(
        "--limit", type=int, default=100, help="Максимум узлов за один запуск (по умолчанию 100)"
    )
    args = parser.parse_args()
    n = asyncio.run(run(limit=args.limit))
    return 0 if n >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
