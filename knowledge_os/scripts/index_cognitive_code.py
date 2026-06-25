#!/usr/bin/env python3
"""
Индексация COGNITIVE_CODE.md и других локальных доков (знания гигантов) в knowledge_nodes.
Узлы попадают в домен AI Research и подтягиваются через RAG по смыслу запроса.

Использование:
  cd knowledge_os && .venv/bin/python scripts/index_cognitive_code.py
  cd knowledge_os && .venv/bin/python scripts/index_cognitive_code.py --file ../docs/THINKING_AND_APPROACH.md
  DATABASE_URL=postgresql://... .venv/bin/python scripts/index_cognitive_code.py --all-docs

Рекомендуемый timeout запуска: ≥ 2 мин при нескольких файлах (эмбеддинги через Ollama).
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Путь для импорта app из knowledge_os
repo_root = Path(__file__).resolve().parent.parent
ko_root = repo_root.parent  # atra-web-ide root (родитель knowledge_os)
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
app_dir = repo_root / "app"
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

try:
    import asyncpg
    from app.semantic_cache import get_embedding
except ImportError as e:
    print(f"Ошибка: нужны asyncpg и app.semantic_cache. {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
DEFAULT_FILES = [
    ko_root / "docs" / "COGNITIVE_CODE.md",
]
# Дополнительные доки «как мы мыслим» и гиганты (опционально)
EXTRA_DOCS = [
    ko_root / "docs" / "THINKING_AND_APPROACH.md",
]
SOURCE_PREFIX = "cognitive_code:"
METADATA_SOURCE = "cognitive_code_indexer"


def chunk_text(text: str, chunk_size: int = 3000, overlap: int = 200):
    """Разбивает текст на чанки (как в index_external_docs)."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - overlap
        if start >= len(text):
            break
    return chunks


async def get_or_create_domain(conn, domain_name: str) -> int:
    domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = $1", domain_name)
    if not domain_id:
        domain_id = await conn.fetchval(
            "INSERT INTO domains (name, description) VALUES ($1, $2) RETURNING id",
            domain_name,
            f"Домен для {domain_name}",
        )
    return domain_id


async def index_one_file(
    conn,
    file_path: Path,
    domain_id: int,
) -> int:
    """
    Индексирует один файл в knowledge_nodes (домен AI Research).
    Сначала удаляет старые чанки этого файла (по source_ref), затем вставляет новые.
    Возвращает количество вставленных чанков.
    """
    if not file_path.is_file():
        logger.warning("Файл не найден: %s", file_path)
        return 0

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error("Ошибка чтения %s: %s", file_path, e)
        return 0

    try:
        file_rel = file_path.relative_to(ko_root)
    except ValueError:
        file_rel = file_path.name

    file_rel_str = str(file_rel).replace("\\", "/")
    source_ref_prefix = f"{SOURCE_PREFIX}{file_rel_str}"

    # Удаляем ранее проиндексированные чанки этого файла (идемпотентный перезапуск)
    deleted = await conn.execute(
        """DELETE FROM knowledge_nodes
           WHERE source_ref LIKE $1""",
        f"{source_ref_prefix}%",
    )
    if deleted and "DELETE" in deleted:
        logger.info("Удалены старые чанки для %s", file_rel_str)

    chunks = chunk_text(content)
    if not chunks:
        return 0

    logger.info("Индексация %s (%s чанков)", file_rel_str, len(chunks))
    inserted = 0
    for i, chunk in enumerate(chunks):
        embedding = await get_embedding(chunk[:8000])  # лимит под размер контекста эмбеддера
        if embedding is None:
            logger.warning("Пропуск чанка %s: эмбеддинг недоступен (Ollama?)", i)
            continue
        metadata = {
            "source": METADATA_SOURCE,
            "file_path": file_rel_str,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "project_context": os.getenv("INDEX_PROJECT_CONTEXT", ""),
            # Системные индексаторы считаем pre-distilled, чтобы не накапливать pending-хвост.
            "distilled": True,
            "distill_status": "done",
            "distilled_by": "system:index_cognitive_code",
        }
        source_ref = f"{source_ref_prefix}#{i}"
        await conn.execute(
            """
            INSERT INTO knowledge_nodes (content, embedding, domain_id, metadata, confidence_score, is_verified, source_ref)
            VALUES ($1, $2::vector, $3, $4, $5, $6, $7)
            """,
            chunk,
            str(embedding),
            domain_id,
            json.dumps(metadata),
            0.85,
            True,
            source_ref,
        )
        inserted += 1
    return inserted


async def run(files: list[Path], use_extra_docs: bool) -> None:
    if not DATABASE_URL:
        logger.error("Задайте DATABASE_URL.")
        sys.exit(1)

    to_index = [p.resolve() if not p.is_absolute() else p for p in files]
    if use_extra_docs:
        for p in EXTRA_DOCS:
            p = p.resolve() if not p.is_absolute() else p
            if p.is_file() and p not in to_index:
                to_index.append(p)

    if not to_index:
        logger.error("Нет файлов для индексации. Укажите --file или --all-docs.")
        sys.exit(1)

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        domain_id = await get_or_create_domain(conn, "AI Research")
        total = 0
        for path in to_index:
            n = await index_one_file(conn, path, domain_id)
            total += n
        logger.info("Готово: проиндексировано чанков: %s", total)
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Индексация COGNITIVE_CODE и доков в RAG (knowledge_nodes)"
    )
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        type=Path,
        help="Путь к файлу (можно несколько раз). По умолчанию только docs/COGNITIVE_CODE.md",
    )
    parser.add_argument(
        "--all-docs",
        action="store_true",
        help="Добавить к списку THINKING_AND_APPROACH.md и др. из EXTRA_DOCS",
    )
    parser.add_argument(
        "--project",
        type=str,
        help="Контекст проекта (slug) для метаданных",
    )
    args = parser.parse_args()

    files = args.files if args.files else DEFAULT_FILES
    # Если указан проект, добавляем его в метаданные через глобальную переменную или аргумент
    os.environ["INDEX_PROJECT_CONTEXT"] = args.project if args.project else ""
    asyncio.run(run(files, use_extra_docs=args.all_docs))


if __name__ == "__main__":
    main()
