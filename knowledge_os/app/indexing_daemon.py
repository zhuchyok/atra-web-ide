import asyncio
import hashlib
import logging
import os
from typing import Optional

import aiohttp
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("IndexingDaemon")

# Конфигурация из окружения
WORKSPACE_ROOT = os.getenv("WORKSPACE_ROOT", os.getcwd())
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:secret@localhost:6432/knowledge_os",  # pragma: allowlist secret
)
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# Расширения файлов для индексации
ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".md",
    ".txt",
    ".sh",
    ".sql",
    ".toml",
    ".yaml",
    ".yml",
}


class IndexingHandler(FileSystemEventHandler):
    """Обработчик событий изменения файлов для индексации."""

    def __init__(self, daemon):
        self.daemon = daemon

    def on_modified(self, event):
        if not event.is_directory and self._is_allowed(event.src_path):
            logger.info(f"📝 Файл изменен: {event.src_path}")
            self.daemon.queue_file(event.src_path)

    def on_created(self, event):
        if not event.is_directory and self._is_allowed(event.src_path):
            logger.info(f"🆕 Файл создан: {event.src_path}")
            self.daemon.queue_file(event.src_path)

    def _is_allowed(self, path):
        try:
            from embedding_eligibility import path_is_indexable
        except ImportError:
            try:
                from app.embedding_eligibility import path_is_indexable
            except ImportError:
                path_is_indexable = lambda p: "venv" not in p.replace("\\", "/")  # noqa: E731
        if not path_is_indexable(path):
            return False
        return any(path.endswith(ext) for ext in ALLOWED_EXTENSIONS)


class IndexingDaemon:
    """Демон фоновой индексации файлов проекта в базу знаний."""

    def __init__(self):
        self.queue = asyncio.Queue()
        self.processed_hashes = {}  # path -> content_hash

    def queue_file(self, path):
        self.queue.put_nowait(path)

    async def get_embedding(self, text: str) -> Optional[list[float]]:
        """Получить эмбеддинг через Ollama."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{OLLAMA_URL.rstrip('/')}/api/embeddings",
                    json={"model": EMBED_MODEL, "prompt": text[:8000]},
                    timeout=10,
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("embedding")
        except Exception as e:
            logger.error(f"❌ Ошибка получения эмбеддинга: {e}")
        return None

    async def index_file(self, path):
        """Проиндексировать один файл."""
        try:
            if not os.path.exists(path):
                return

            try:
                from embedding_eligibility import path_is_indexable
            except ImportError:
                from app.embedding_eligibility import path_is_indexable

            if not path_is_indexable(path):
                logger.debug("Skip non-indexable path: %s", path)
                return

            with open(path, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if not content.strip():
                return

            content_hash = hashlib.md5(content.encode()).hexdigest()
            if self.processed_hashes.get(path) == content_hash:
                return  # Файл не изменился содержательно

            logger.info(f"🔍 Индексация: {path}")
            embedding = await self.get_embedding(content)
            if not embedding:
                return

            import asyncpg

            conn = await asyncpg.connect(DB_URL)
            try:
                # Сохраняем в knowledge_nodes
                # domain_id для проектных файлов (создаем если нет)
                domain_id = await conn.fetchval(
                    "SELECT id FROM domains WHERE name = 'project_files' LIMIT 1"
                )
                if not domain_id:
                    domain_id = await conn.fetchval(
                        "INSERT INTO domains (name, description) VALUES ('project_files', 'Project source files') RETURNING id"
                    )

                # Очищаем старые записи для этого файла
                await conn.execute(
                    "DELETE FROM knowledge_nodes WHERE metadata->>'file_path' = $1", path
                )

                # [SINGULARITY 21.8] project_slug для фильтрации RAG по проекту (аудит setki-21)
                project_slug = None
                try:
                    rows = await conn.fetch(
                        "SELECT slug, workspace_path FROM projects WHERE is_active = true"
                    )
                    path_norm = os.path.normpath(path)
                    for row in rows:
                        wp = (row["workspace_path"] or "").strip()
                        if not wp:
                            continue
                        wp_norm = os.path.normpath(wp)
                        if path_norm.startswith(wp_norm) or row["slug"] in path_norm:
                            project_slug = row["slug"]
                            break
                except Exception as e:
                    logger.debug(f"Project slug resolution: {e}")

                import json as _json

                # Content prefix for legacy PROJECT_FILE rows — never write venv paths
                rel = path
                try:
                    rel = os.path.relpath(path, WORKSPACE_ROOT)
                except ValueError:
                    rel = path
                content_kn = f'PROJECT_FILE: "{rel}"\n\n{content[:10000]}'

                metadata_obj = {
                    "file_path": path,
                    "source": "indexing_daemon",
                    "type": "project_file",
                    "rag_eligible": True,
                }
                if project_slug:
                    metadata_obj["project_slug"] = project_slug
                metadata_json = _json.dumps(metadata_obj, ensure_ascii=False)

                # Вставляем новую запись
                await conn.execute(
                    """
                    INSERT INTO knowledge_nodes (content, domain_id, confidence_score, embedding, is_verified, metadata)
                    VALUES ($1, $2, 1.0, $3, TRUE, $4::jsonb)
                """,
                    content_kn,
                    domain_id,
                    embedding,
                    metadata_json,
                )

                self.processed_hashes[path] = content_hash
                logger.info(f"✅ Проиндексирован: {path}")
            finally:
                await conn.close()

        except Exception as e:
            logger.error(f"❌ Ошибка индексации {path}: {e}")

    async def worker(self):
        """Воркер для обработки очереди."""
        while True:
            path = await self.queue.get()
            await self.index_file(path)
            self.queue.task_done()
            await asyncio.sleep(1)  # Небольшая пауза между файлами

    async def initial_scan(self):
        """Первоначальное сканирование всего проекта."""
        logger.info(f"🚀 Начало первичного сканирования: {WORKSPACE_ROOT}")
        skip_dirs = {
            ".git",
            "node_modules",
            ".venv",
            "venv",
            "__pycache__",
            "dist",
            "build",
            "site-packages",
            ".tox",
            ".mypy_cache",
            ".ruff_cache",
        }
        for root, dirs, files in os.walk(WORKSPACE_ROOT):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            if any(part in skip_dirs for part in root.replace("\\", "/").split("/")):
                continue
            for file in files:
                path = os.path.join(root, file)
                if any(path.endswith(ext) for ext in ALLOWED_EXTENSIONS):
                    self.queue_file(path)
        logger.info("📡 Первичное сканирование завершено, файлы в очереди")

    async def run(self):
        """Запуск демона."""
        # Запуск воркера
        worker_task = asyncio.create_task(self.worker())

        # Первичный скан
        await self.initial_scan()

        # Настройка watchdog
        observer = Observer()
        observer.schedule(IndexingHandler(self), WORKSPACE_ROOT, recursive=True)
        observer.start()

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            observer.stop()
        observer.join()
        worker_task.cancel()


if __name__ == "__main__":
    daemon = IndexingDaemon()
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        pass
