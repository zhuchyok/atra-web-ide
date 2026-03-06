#!/usr/bin/env python3
"""
Автоматическая регистрация и индексация всех проектов в папке dev/.
Виктория сканирует директорию, находит новые проекты и изучает их.
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEV_DIR = Path("/workspace/dev")
MAIN_PROJECT_PATH = Path("/workspace/atra-web-ide")
DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@knowledge_postgres:5432/knowledge_os")


async def register_project(conn, slug, name, path):
    """Регистрирует проект в таблице projects."""
    logger.info(f"📝 Регистрация проекта: {slug} ({name})")
    await conn.execute(
        """
        INSERT INTO projects (slug, name, workspace_path, is_active)
        VALUES ($1, $2, $3, true)
        ON CONFLICT (slug) DO UPDATE
        SET name = EXCLUDED.name, workspace_path = EXCLUDED.workspace_path
        """,
        slug,
        name,
        str(path),
    )


async def index_project(slug, path):
    """Запускает индексацию файлов проекта."""
    logger.info(f"🧠 Изучение проекта: {slug}...")

    # Ищем ключевые файлы для индексации
    files_to_index = []
    for pattern in ["README.md", "MASTER_REFERENCE.md", "docs/*.md", "src/**/*.rs", "src/**/*.py"]:
        found = list(path.glob(pattern))
        files_to_index.extend(found)

    if not files_to_index:
        logger.warning(f"⚠️ В проекте {slug} не найдено файлов для индексации.")
        return

    # Формируем команду для индексатора
    cmd = ["python3", "knowledge_os/scripts/index_cognitive_code.py", "--project", slug]
    for f in files_to_index[:20]:  # Лимит 20 файлов для начала, чтобы не перегрузить
        cmd.extend(["--file", str(f)])

    try:
        # Запускаем внутри контейнера (скрипт уже там)
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"✅ Проект {slug} успешно проиндексирован.")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Ошибка индексации {slug}: {e.stderr}")


async def main():
    if not DEV_DIR.exists():
        logger.error(f"Папка {DEV_DIR} не найдена.")
        return

    conn = await asyncpg.connect(DB_URL)
    try:
        # 1. Сканируем dev/
        projects = [d for d in DEV_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]

        # Добавляем основной проект
        projects.append(MAIN_PROJECT_PATH)

        for p_path in projects:
            slug = p_path.name
            name = slug.replace("-", " ").title()

            # Регистрируем
            await register_project(conn, slug, name, p_path)

            # Индексируем
            await index_project(slug, p_path)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
