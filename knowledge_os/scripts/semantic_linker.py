#!/usr/bin/env python3
"""
Knowledge OS: Semantic Linker (v3.0 - Slow Mode)
Автоматическая перелинковка Базы Знаний для создания Карты Разума.
Работает не спеша, порциями, чтобы не перегружать систему.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _setup_path():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo not in sys.path:
        sys.path.insert(0, repo)
    app_dir = os.path.join(repo, "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)


async def link_knowledge_nodes(limit: int = 1000, threshold: float = 0.60):
    """
    Находит близкие по смыслу узлы и создает связи в knowledge_links (Slow Mode).
    """
    _setup_path()
    try:
        import asyncpg
    except ImportError:
        logger.error("Требуется asyncpg")
        return

    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    conn = await asyncpg.connect(db_url)

    try:
        # [SLOW MODE] Обрабатываем небольшими пачками
        batch_size = 50
        nodes = await conn.fetch(
            """
            SELECT id, content, embedding
            FROM knowledge_nodes
            WHERE embedding IS NOT NULL
            ORDER BY created_at DESC
            LIMIT $1
        """,
            limit,
        )

        logger.info(f"🐢 Начинаем неспешную перелинковку {len(nodes)} узлов")
        links_created = 0

        for i, node in enumerate(nodes):
            node_id = node["id"]
            embedding = node["embedding"]

            # Ищем похожие узлы через отрицательное скалярное произведение
            similar_nodes = await conn.fetch(
                """
                SELECT id, (embedding <#> $1::vector) as dot
                FROM knowledge_nodes
                WHERE id != $2
                  AND embedding IS NOT NULL
                ORDER BY embedding <#> $1::vector ASC
                LIMIT 10
            """,
                embedding,
                node_id,
            )

            for sim_node in similar_nodes:
                dot_val = sim_node["dot"]
                # Порог для dot product (чем меньше/отрицательнее, тем лучше)
                if dot_val is None or dot_val > -50:
                    continue

                try:
                    await conn.execute(
                        """
                        INSERT INTO knowledge_links (source_node_id, target_node_id, link_type, metadata)
                        VALUES ($1, $2, 'semantic_similarity', $3)
                        ON CONFLICT DO NOTHING
                    """,
                        node_id,
                        sim_node["id"],
                        json.dumps(
                            {
                                "dot_product": float(dot_val),
                                "created_by": "semantic_linker_v3_slow",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        ),
                    )
                    links_created += 1
                except Exception:
                    pass

            # [SLOW MODE] Пауза между узлами, чтобы не греть Mac Studio
            if (i + 1) % batch_size == 0:
                logger.info(
                    f"Обработано {i + 1}/{len(nodes)} узлов, создано {links_created} связей. Пауза 5 сек..."
                )
                await asyncio.sleep(5)

        logger.info(f"✅ Неспешная перелинковка завершена! Создано связей: {links_created}")
        return links_created

    finally:
        await conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Knowledge OS Semantic Linker (Slow)")
    parser.add_argument("--limit", type=int, default=500, help="Количество узлов для анализа")
    args = parser.parse_args()

    asyncio.run(link_knowledge_nodes(limit=args.limit))
