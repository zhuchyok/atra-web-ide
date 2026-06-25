#!/usr/bin/env python3
"""
Скрипт для индексации внешних документов (промптов, документации) в Knowledge OS.
Выкачивает репозитории и индексирует содержимое в таблицу knowledge_nodes.
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import subprocess
import sys
from typing import List, Optional

# Настройка путей для импорта из knowledge_os
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
app_dir = os.path.join(repo_root, "app")
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

try:
    import asyncpg
    from app.semantic_cache import get_embedding
except ImportError:
    print("Ошибка: Необходимы asyncpg и app.semantic_cache. Проверьте установку зависимостей.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REPOS = ["https://github.com/asgeirtj/system_prompts_leaks.git"]

TARGET_DIR = os.path.join(repo_root, "knowledge_base", "ai_research")
DATABASE_URL = os.getenv("DATABASE_URL")


async def get_or_create_domain(conn, domain_name: str) -> int:
    """Получает ID домена или создает новый."""
    domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = $1", domain_name)
    if not domain_id:
        domain_id = await conn.fetchval(
            "INSERT INTO domains (name, description) VALUES ($1, $2) RETURNING id",
            domain_name,
            f"Домен для {domain_name}",
        )
    return domain_id


def chunk_text(text: str, chunk_size: int = 3000, overlap: int = 200) -> List[str]:
    """Разбивает текст на чанки."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


async def index_file(conn, file_path: str, domain_id: int):
    """Индексирует один файл."""
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Ошибка чтения файла {file_path}: {e}")
        return

    file_rel_path = os.path.relpath(file_path, TARGET_DIR)
    file_hash = hashlib.sha256(content.encode()).hexdigest()

    # Проверка на дубликаты
    exists = await conn.fetchval(
        "SELECT id FROM knowledge_nodes WHERE metadata->>'file_hash' = $1", file_hash
    )
    if exists:
        logger.debug(f"Файл {file_rel_path} уже проиндексирован.")
        return

    chunks = chunk_text(content)
    logger.info(f"Индексация {file_rel_path} ({len(chunks)} чанков)")

    for i, chunk in enumerate(chunks):
        embedding = await get_embedding(chunk)
        metadata = {
            "source": "external_docs_indexer",
            "file_path": file_rel_path,
            "file_hash": file_hash,
            "chunk_index": i,
            "total_chunks": len(chunks),
            # Индексированные внешние знания готовы к использованию без отдельной дистилляции.
            "distilled": True,
            "distill_status": "done",
            "distilled_by": "system:index_external_docs",
        }

        await conn.execute(
            """
            INSERT INTO knowledge_nodes (content, embedding, domain_id, metadata, confidence_score, is_verified, source_ref)
            VALUES ($1, $2::vector, $3, $4, $5, $6, $7)
            """,
            chunk,
            str(embedding) if embedding else None,
            domain_id,
            json.dumps(metadata),
            0.8,
            True,
            f"github:system_prompts_leaks/{file_rel_path}",
        )


def _sync_repo(repo_url: str, repo_path: str) -> None:
    """Синхронизирует репозиторий с защитой от битого worktree."""
    if not os.path.exists(repo_path):
        logger.info(f"Клонирование {repo_url}...")
        subprocess.run(["git", "clone", repo_url, repo_path], check=True)
        return

    logger.info(f"Обновление {os.path.basename(repo_path)}...")
    try:
        subprocess.run(["git", "-C", repo_path, "pull", "--ff-only"], check=True)
        return
    except subprocess.CalledProcessError as pull_err:
        logger.warning(f"git pull не удался: {pull_err}. Пробуем self-heal...")

    # Fallback: аккуратно восстанавливаем состояние без удаления каталога.
    subprocess.run(["git", "-C", repo_path, "fetch", "--all", "--prune"], check=True)
    subprocess.run(["git", "-C", repo_path, "checkout", "-f", "origin/main"], check=True)
    subprocess.run(["git", "-C", repo_path, "checkout", "-B", "main", "origin/main"], check=True)
    subprocess.run(["git", "-C", repo_path, "reset", "--hard", "origin/main"], check=True)
    logger.info("Self-heal git-репозитория завершен.")


def _iter_indexable_files(max_files: Optional[int] = None):
    """Итерирует индексируемые файлы (по расширениям) с опциональным лимитом."""
    yielded = 0
    for root, _, files in os.walk(TARGET_DIR):
        files.sort()
        for file in files:
            if not file.endswith((".md", ".txt", ".json")):
                continue
            yield os.path.join(root, file)
            yielded += 1
            if max_files is not None and yielded >= max_files:
                return


async def run_indexing(max_files: Optional[int] = None, report_every: int = 100):
    """Основной цикл индексации."""
    if not DATABASE_URL:
        logger.error("DATABASE_URL не задан.")
        return

    # 1. Выкачивание репозиториев
    os.makedirs(TARGET_DIR, exist_ok=True)
    for repo_url in REPOS:
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        repo_path = os.path.join(TARGET_DIR, repo_name)
        _sync_repo(repo_url, repo_path)

    # 2. Индексация
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        domain_id = await get_or_create_domain(conn, "AI Research")
        processed = 0
        for file_path in _iter_indexable_files(max_files=max_files):
            await index_file(conn, file_path, domain_id)
            processed += 1
            if report_every > 0 and processed % report_every == 0:
                logger.info("Прогресс индексации: %s файлов", processed)
        logger.info("Индексация завершена: обработано файлов: %s", processed)
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Индексация внешних документов в AI Research")
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Лимит количества файлов для одного прогона (по умолчанию без лимита).",
    )
    parser.add_argument(
        "--report-every",
        type=int,
        default=100,
        help="Период логирования прогресса в файлах (по умолчанию 100).",
    )
    args = parser.parse_args()
    asyncio.run(run_indexing(max_files=args.max_files, report_every=args.report_every))
