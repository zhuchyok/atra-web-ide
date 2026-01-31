"""
Unified Embedding Provider — кэширование эмбеддингов в рамках одного запроса.
Ollama (embeddings) + MLX (LLM): один эмбеддинг на запрос для RAG + semantic cache.
Снижает вызовы Ollama при нескольких компонентах (RAG context + semantic cache lookup).
"""
import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class UnifiedEmbeddingProvider:
    """Кэш эмбеддингов в рамках одного запроса (request-scoped)."""

    def __init__(self, get_embedding_func):
        """
        Args:
            get_embedding_func: async (text: str) -> Optional[List[float]]
        """
        self._get_embedding = get_embedding_func
        self._request_embeddings: Dict[str, List[float]] = {}
        self._request_id: Optional[str] = None

    @asynccontextmanager
    async def request_scope(self, request_id: str):
        """Контекст для одного запроса — эмбеддинги переиспользуются."""
        try:
            self._request_id = request_id
            self._request_embeddings.clear()
            yield self
        finally:
            self._request_id = None
            self._request_embeddings.clear()

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Получить эмбеддинг (из кэша запроса или вычислить)."""
        if not text:
            return None
        key = text.strip().lower()[:500]
        if key in self._request_embeddings:
            return self._request_embeddings[key]
        emb = await self._get_embedding(text)
        if emb:
            self._request_embeddings[key] = emb
        return emb

    def get_cached_only(self, text: str) -> Optional[List[float]]:
        """Быстрая проверка без вызова Ollama."""
        key = text.strip().lower()[:500]
        return self._request_embeddings.get(key)
