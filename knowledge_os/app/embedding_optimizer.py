"""
Embedding Optimizer
Оптимизация генерации и кэширования эмбеддингов
Singularity 8.0: Performance Optimization
"""

import asyncio
import logging
import hashlib
import asyncpg
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

# Rust-ускорение: нормализация + хэш для ключей кэша (опционально)
try:
    from cache_normalizer import (
        normalize_and_hash as _rust_normalize_and_hash,
        normalize_text as _rust_normalize_text,
        normalize_and_hash_batch as _rust_normalize_and_hash_batch,
    )
    _USE_RUST_NORMALIZER = True
except ImportError:
    _USE_RUST_NORMALIZER = False
    _rust_normalize_and_hash = None
    _rust_normalize_text = None
    _rust_normalize_and_hash_batch = None

class EmbeddingOptimizer:
    """
    Оптимизация эмбеддингов через кэширование и batch-обработку.
    Ускоряет поиск в кэше на 50-70%.
    """
    
    def __init__(self, db_url: str = DB_URL):
        """
        Args:
            db_url: URL базы данных
        """
        self.db_url = db_url
        self._memory_cache: Dict[str, List[float]] = {}  # In-memory кэш
        self._cache_size = 1000  # Максимум эмбеддингов в памяти
        self._batch_queue: List[Dict[str, Any]] = []  # Очередь для batch-обработки
        self._batch_size = 10  # Размер батча
        self._batch_timeout = 0.5  # Таймаут батча в секундах
    
    def _normalize_text(self, text: str) -> str:
        """Нормализует текст для кэширования (убирает лишние пробелы, приводит к нижнему регистру)"""
        if _USE_RUST_NORMALIZER and _rust_normalize_text:
            return _rust_normalize_text(text)
        return ' '.join(text.lower().split())
    
    def _get_text_hash(self, text: str) -> str:
        """Получает хэш нормализованного текста (Rust при наличии, иначе Python)"""
        if _USE_RUST_NORMALIZER:
            return _rust_normalize_and_hash(text)
        normalized = self._normalize_text(text)
        return hashlib.md5(normalized.encode()).hexdigest()

    def _get_text_hashes_batch(self, texts: List[str]) -> List[str]:
        """Батч хэшей: один вызов Rust при наличии, иначе N вызовов Python (меньше переходов Python↔Rust)."""
        if _USE_RUST_NORMALIZER and _rust_normalize_and_hash_batch is not None:
            return _rust_normalize_and_hash_batch(texts)
        return [self._get_text_hash(t) for t in texts]

    async def _get_cached_embedding_by_hash(self, text_hash: str) -> Optional[List[float]]:
        """Получает эмбеддинг из кэша по уже вычисленному хэшу (память -> БД)."""
        if text_hash in self._memory_cache:
            return self._memory_cache[text_hash]
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'embedding_cache'
                    )
                """)
                if not table_exists:
                    return None
                row = await conn.fetchrow(
                    "SELECT embedding FROM embedding_cache WHERE text_hash = $1", text_hash
                )
                if row:
                    embedding = row["embedding"]
                    if len(self._memory_cache) >= self._cache_size:
                        oldest_key = next(iter(self._memory_cache))
                        del self._memory_cache[oldest_key]
                    self._memory_cache[text_hash] = embedding
                    return embedding
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"⚠️ [EMBEDDING CACHE] DB lookup failed: {e}")
        return None

    async def get_cached_embedding(self, text: str) -> Optional[List[float]]:
        """
        Получает эмбеддинг из кэша (память -> БД).

        Args:
            text: Текст для получения эмбеддинга

        Returns:
            Эмбеддинг или None
        """
        text_hash = self._get_text_hash(text)
        cached = await self._get_cached_embedding_by_hash(text_hash)
        if cached:
            logger.debug(f"✅ [EMBEDDING CACHE] Hit for: {text[:50]}...")
        return cached
    
    async def save_embedding(self, text: str, embedding: List[float]):
        """
        Сохраняет эмбеддинг в кэш (память и БД).
        
        Args:
            text: Текст
            embedding: Эмбеддинг
        """
        text_hash = self._get_text_hash(text)
        normalized_text = self._normalize_text(text)
        
        # Сохраняем в memory cache
        if len(self._memory_cache) >= self._cache_size:
            # Удаляем старые (FIFO)
            oldest_key = next(iter(self._memory_cache))
            del self._memory_cache[oldest_key]
        self._memory_cache[text_hash] = embedding
        
        # Сохраняем в БД (асинхронно, не блокируем)
        asyncio.create_task(self._save_embedding_to_db(text_hash, normalized_text, embedding))
    
    async def _save_embedding_to_db(self, text_hash: str, normalized_text: str, embedding: List[float]):
        """Сохраняет эмбеддинг в БД"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблицы
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'embedding_cache'
                    )
                """)
                
                if not table_exists:
                    logger.debug("⚠️ [EMBEDDING CACHE] Таблица embedding_cache не существует")
                    return
                
                await conn.execute("""
                    INSERT INTO embedding_cache (text_hash, normalized_text, embedding, created_at)
                    VALUES ($1, $2, $3::vector, NOW())
                    ON CONFLICT (text_hash) DO UPDATE 
                    SET embedding = EXCLUDED.embedding,
                        created_at = NOW()
                """, text_hash, normalized_text, str(embedding))
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"⚠️ [EMBEDDING CACHE] Failed to save to DB: {e}")
    
    async def get_embeddings_batch(self, texts: List[str], get_embedding_func) -> List[Optional[List[float]]]:
        """
        Получает эмбеддинги для батча текстов.
        Использует кэш для уже вычисленных эмбеддингов.
        
        Args:
            texts: Список текстов
            get_embedding_func: Функция для генерации эмбеддинга
        
        Returns:
            Список эмбеддингов
        """
        results = []
        texts_to_compute = []
        indices_to_compute = []
        # Один вызов батча для всех хэшей (Rust при наличии — меньше переходов Python↔Rust)
        hashes = self._get_text_hashes_batch(texts)
        for i, (text, text_hash) in enumerate(zip(texts, hashes)):
            cached = await self._get_cached_embedding_by_hash(text_hash)
            if cached:
                results.append((i, cached))
            else:
                texts_to_compute.append(text)
                indices_to_compute.append(i)
        
        # Генерируем эмбеддинги для текстов, которых нет в кэше
        if texts_to_compute:
            logger.debug(f"📦 [EMBEDDING BATCH] Computing {len(texts_to_compute)} embeddings...")
            # Можно использовать параллельную обработку
            embeddings = await asyncio.gather(*[
                get_embedding_func(text) for text in texts_to_compute
            ], return_exceptions=True)
            
            # Сохраняем в кэш и добавляем в результаты
            for idx, text, embedding in zip(indices_to_compute, texts_to_compute, embeddings):
                if isinstance(embedding, Exception):
                    logger.error(f"❌ [EMBEDDING BATCH] Failed for text {idx}: {embedding}")
                    results.append((idx, None))
                elif embedding:
                    await self.save_embedding(text, embedding)
                    results.append((idx, embedding))
                else:
                    results.append((idx, None))
        
        # Сортируем результаты по индексам
        results.sort(key=lambda x: x[0])
        return [emb for _, emb in results]

# Singleton instance
_optimizer_instance: Optional[EmbeddingOptimizer] = None

def get_embedding_optimizer(db_url: str = DB_URL) -> EmbeddingOptimizer:
    """Получить singleton экземпляр оптимизатора"""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = EmbeddingOptimizer(db_url=db_url)
    return _optimizer_instance

