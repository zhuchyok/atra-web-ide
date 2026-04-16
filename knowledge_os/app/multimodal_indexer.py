import os
import logging
import asyncio
import json
from typing import List, Dict, Any
from datetime import datetime, timezone
import httpx
from PIL import Image
import io
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VISUAL_SEARCH_URL = os.getenv("VISUAL_SEARCH_URL", "http://victoria-visual-search:8005")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os")
CORPUS_DIRS = ["/app/corpus/docs", "/app/corpus/knowledge_os", "/app/corpus/frontend"]
# Max chars to embed per markdown doc (avoids context overflow with nomic-embed-text)
MD_MAX_CHARS = int(os.getenv("MD_MAX_CHARS", "4000"))
SUPPORTED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.pdf', '.md', '.txt')


class MultimodalIndexer:
    """
    Индексатор мультимодальных и текстовых данных (MD, изображения, PDF).
    Использует nomic-embed-text через Ollama для реальных эмбеддингов.
    """

    def __init__(self):
        self.db_url = DATABASE_URL
        self.visual_search_url = VISUAL_SEARCH_URL

    async def scan_and_index(self):
        """Сканирует директории и индексирует новые файлы."""
        logger.info("🚀 Starting multimodal indexing cycle...")

        files_to_index = self._get_files_to_index()
        logger.info(f"📂 Found {len(files_to_index)} potential artifacts.")

        indexed = 0
        skipped = 0
        for file_path in files_to_index:
            try:
                result = await self._index_file(file_path)
                if result:
                    indexed += 1
            except Exception as e:
                logger.error(f"❌ Failed to index {file_path}: {e}")
                skipped += 1

        logger.info(f"✅ Indexing cycle complete. Indexed: {indexed}, Skipped/Failed: {skipped}")

    def _get_files_to_index(self) -> List[str]:
        """Возвращает список путей к поддерживаемым файлам."""
        found_files = []
        for corpus_dir in CORPUS_DIRS:
            if not os.path.exists(corpus_dir):
                logger.warning(f"⚠️ Directory not found: {corpus_dir}")
                continue

            for root, dirs, files in os.walk(corpus_dir):
                # Skip hidden dirs, node_modules, __pycache__
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', '__pycache__', '.git')]
                for file in files:
                    if file.lower().endswith(SUPPORTED_EXTENSIONS):
                        found_files.append(os.path.join(root, file))
        return found_files

    async def _index_file(self, file_path: str) -> bool:
        """Индексирует один файл. Возвращает True если успешно."""
        ext = os.path.splitext(file_path)[1].lower()

        if ext in ('.md', '.txt'):
            return await self._index_text_file(file_path)
        elif ext in ('.png', '.jpg', '.jpeg', '.pdf'):
            return await self._index_visual_file(file_path)
        return False

    async def _index_text_file(self, file_path: str) -> bool:
        """Индексирует текстовый/markdown файл через /index endpoint."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()[:MD_MAX_CHARS]

            if not content.strip():
                return False

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.visual_search_url}/index",
                    json={"file_path": file_path, "text_content": content}
                )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Indexed text: {os.path.basename(file_path)}")
                await self._register_in_db(file_path, result.get("embedding_id"), artifact_type="text_doc")
                return True
            else:
                logger.error(f"❌ Service error for {file_path}: {response.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"❌ Text indexing failed for {file_path}: {e}")
            return False

    async def _index_visual_file(self, file_path: str) -> bool:
        """Индексирует визуальный артефакт (изображение, PDF)."""
        logger.info(f"🔍 Indexing visual: {file_path}")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.visual_search_url}/index",
                json={"file_path": file_path}
            )

        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Indexed visual: {os.path.basename(file_path)}")
            await self._register_in_db(file_path, result.get("embedding_id"), artifact_type="visual_artifact")
            return True
        else:
            logger.error(f"❌ Visual service error for {file_path}: {response.text[:200]}")
            return False

    async def _register_in_db(self, file_path: str, embedding_id: str, artifact_type: str = "visual_artifact"):
        """Регистрирует метаданные в knowledge_nodes."""
        import asyncpg
        conn = await asyncpg.connect(self.db_url)
        try:
            exists = await conn.fetchval(
                "SELECT id FROM knowledge_nodes WHERE source_ref = $1", file_path
            )

            metadata = {
                "type": artifact_type,
                "file_path": file_path,
                "embedding_id": embedding_id,
                "indexed_at": datetime.now(timezone.utc).isoformat()
            }

            if not exists:
                await conn.execute(
                    """
                    INSERT INTO knowledge_nodes (content, metadata, confidence_score, source_ref)
                    VALUES ($1, $2, $3, $4)
                    """,
                    f"{artifact_type}: {os.path.basename(file_path)}",
                    json.dumps(metadata),
                    1.0,
                    file_path
                )
                logger.info(f"📝 Registered in DB: {os.path.basename(file_path)}")
            else:
                await conn.execute(
                    "UPDATE knowledge_nodes SET metadata = $1, updated_at = NOW() WHERE id = $2",
                    json.dumps(metadata),
                    exists
                )
        finally:
            await conn.close()


if __name__ == "__main__":
    indexer = MultimodalIndexer()
    asyncio.run(indexer.scan_and_index())
