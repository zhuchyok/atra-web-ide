#!/usr/bin/env python3
"""
Скрипт для индексации внешних документов (промптов, документации) в Knowledge OS.
Выкачивает репозитории и индексирует содержимое в таблицу knowledge_nodes.
"""

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

REPOS = [
    "https://github.com/asgeirtj/system_prompts_leaks.git",
    "https://github.com/openai/openai-cookbook.git",  # Примеры и рецепты OpenAI
    "https://github.com/deepseek-ai/DeepSeek-V3.git",  # Документация и архитектура DeepSeek
    "https://github.com/langchain-ai/langchain.git",  # Основной фреймворк для RAG/LLM
    "https://github.com/microsoft/autogen.git",  # Агенты от Microsoft
]
URLS = ["https://docs.anthropic.com/en/docs/welcome"]

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
        with open(file_path, encoding="utf-8") as f:
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


async def index_url(conn, url: str, domain_id: int):
    """Индексирует контент по произвольному URL."""
    try:
        import httpx
        from bs4 import BeautifulSoup

        logger.info(f"Загрузка контента с {url}...")
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        # Убираем скрипты и стили
        for script in soup(["script", "style"]):
            script.extract()

        text = soup.get_text(separator=" ", strip=True)
        if not text:
            logger.warning(f"Пустой контент по URL: {url}")
            return

        url_hash = hashlib.sha256(url.encode()).hexdigest()

        # Проверка на дубликаты
        exists = await conn.fetchval(
            "SELECT id FROM knowledge_nodes WHERE metadata->>'source_url_hash' = $1", url_hash
        )
        if exists:
            logger.debug(f"URL {url} уже проиндексирован.")
            return

        chunks = chunk_text(text)
        logger.info(f"Индексация URL {url} ({len(chunks)} чанков)")

        for i, chunk in enumerate(chunks):
            embedding = await get_embedding(chunk)
            metadata = {
                "source": "external_docs_indexer",
                "source_url": url,
                "source_url_hash": url_hash,
                "chunk_index": i,
                "total_chunks": len(chunks),
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
                f"url:{url}",
            )
    except Exception as e:
        logger.error(f"Ошибка индексации URL {url}: {e}")


async def run_indexing():
    """Основной цикл индексации."""
    if not DATABASE_URL:
        logger.error("DATABASE_URL не задан.")
        return

    # 1. Выкачивание репозиториев
    os.makedirs(TARGET_DIR, exist_ok=True)
    for repo_url in REPOS:
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        repo_path = os.path.join(TARGET_DIR, repo_name)
        if not os.path.exists(repo_path):
            logger.info(f"Клонирование {repo_url}...")
            try:
                subprocess.run(["git", "clone", repo_url, repo_path], check=True)
            except Exception as e:
                logger.error(f"Ошибка клонирования {repo_url}: {e}")
        else:
            logger.info(f"Обновление {repo_name}...")
            try:
                subprocess.run(["git", "-C", repo_path, "pull"], check=True)
            except Exception as e:
                logger.error(f"Ошибка обновления {repo_name}: {e}")

    # 2. Индексация
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        domain_id = await get_or_create_domain(conn, "AI Research")

        # Индексация файлов из репозиториев
        for root, _, files in os.walk(TARGET_DIR):
            for file in files:
                if file.endswith((".md", ".txt", ".json")):
                    await index_file(conn, os.path.join(root, file), domain_id)

        # Индексация произвольных URL
        for url in URLS:
            await index_url(conn, url, domain_id)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_indexing())
