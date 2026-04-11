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

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
VISUAL_SEARCH_URL = os.getenv("VISUAL_SEARCH_URL", "http://victoria-visual-search:8005")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os")
CORPUS_DIRS = ["/app/corpus/docs", "/app/corpus/frontend"]

class MultimodalIndexer:
    """
    Индексатор для мультимодальных данных (изображения, PDF).
    Использует сервис victoria-visual-search для генерации эмбеддингов и FAISS.
    """

    def __init__(self):
        self.db_url = DATABASE_URL
        self.visual_search_url = VISUAL_SEARCH_URL

    async def scan_and_index(self):
        """Сканирует директории и индексирует новые файлы."""
        logger.info("🚀 Starting multimodal indexing cycle...")
        
        files_to_index = self._get_files_to_index()
        logger.info(f"📂 Found {len(files_to_index)} potential visual artifacts.")

        for file_path in files_to_index:
            try:
                await self._index_file(file_path)
            except Exception as e:
                logger.error(f"❌ Failed to index {file_path}: {e}")

        logger.info("✅ Multimodal indexing cycle completed.")

    def _get_files_to_index(self) -> List[str]:
        """Возвращает список путей к файлам (png, jpg, pdf)."""
        found_files = []
        for corpus_dir in CORPUS_DIRS:
            if not os.path.exists(corpus_dir):
                logger.warning(f"⚠️ Directory not found: {corpus_dir}")
                continue
            
            for root, _, files in os.walk(corpus_dir):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf')):
                        found_files.append(os.path.join(root, file))
        return found_files

    async def _index_file(self, file_path: str):
        """Индексирует один файл."""
        logger.info(f"🔍 Indexing: {file_path}")
        
        # 1. Подготовка изображения (для PDF — первая страница или превью)
        # В этой версии мы просто отправляем путь в сервис, так как он имеет доступ к тем же томам
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.visual_search_url}/index",
                json={"file_path": file_path}
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Successfully indexed in FAISS: {file_path}")
                
                # 2. Регистрация в PostgreSQL
                await self._register_in_db(file_path, result.get("embedding_id"))
            else:
                logger.error(f"❌ Visual search service error for {file_path}: {response.text}")

    async def _register_in_db(self, file_path: str, embedding_id: str):
        """Регистрирует метаданные в таблице knowledge_nodes."""
        import asyncpg
        conn = await asyncpg.connect(self.db_url)
        try:
            # Проверяем, есть ли уже такой узел
            exists = await conn.fetchval(
                "SELECT id FROM knowledge_nodes WHERE source_ref = $1", file_path
            )
            
            metadata = {
                "type": "visual_artifact",
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
                    f"Visual artifact: {os.path.basename(file_path)}",
                    json.dumps(metadata),
                    1.0,
                    file_path
                )
                logger.info(f"📝 Registered in DB: {file_path}")
            else:
                await conn.execute(
                    "UPDATE knowledge_nodes SET metadata = $1, updated_at = NOW() WHERE id = $2",
                    json.dumps(metadata),
                    exists
                )
                logger.info(f"🔄 Updated in DB: {file_path}")
        finally:
            await conn.close()

if __name__ == "__main__":
    indexer = MultimodalIndexer()
    asyncio.run(indexer.scan_and_index())
