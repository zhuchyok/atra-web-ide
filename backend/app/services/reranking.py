"""
Фаза 4, неделя 1: реранкинг чанков для повышения релевантности RAG.

Методы: cross_encoder (точнее, медленнее), text_similarity (быстрее), hybrid.
Интеграция: опционально в RAG-light после поиска по вектору.
"""

import logging
import re
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Опционально: sentence-transformers для cross-encoder
try:
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    CrossEncoder = None


class RerankingService:
    """
    Сервис реранкинга чанков по запросу.
    Повышает релевантность выдачи при сохранении приемлемой латентности.
    """

    def __init__(
        self,
        method: str = "text_similarity",
        model_name: Optional[str] = None,
        top_k: int = 5,
    ):
        self.method = method
        self.top_k = top_k
        self._cross_encoder = None
        if method == "cross_encoder" and CROSS_ENCODER_AVAILABLE and CrossEncoder:
            try:
                self._cross_encoder = CrossEncoder(model_name or "cross-encoder/ms-marco-MiniLM-L-6-v2")
            except Exception as e:
                logger.warning("CrossEncoder init failed, fallback to text_similarity: %s", e)
                self.method = "text_similarity"

    async def rerank_chunks(
        self,
        query: str,
        chunks: List[str],
        method: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> List[str]:
        """
        Реранкинг чанков по релевантности к запросу.
        Возвращает топ top_k чанков в порядке убывания релевантности.
        """
        if not chunks:
            return []
        m = method or self.method
        k = min(top_k or self.top_k, len(chunks))

        if m == "cross_encoder" and self._cross_encoder:
            return await self._rerank_cross_encoder(query, chunks, k)
        if m == "hybrid":
            return await self._rerank_hybrid(query, chunks, k)
        return await self._rerank_text_similarity(query, chunks, k)

    async def _rerank_cross_encoder(
        self, query: str, chunks: List[str], top_k: int
    ) -> List[str]:
        """Реранкинг через cross-encoder (точнее, но медленнее)."""
        try:
            pairs = [(query, c) for c in chunks]
            scores = self._cross_encoder.predict(pairs)
            indexed = list(zip(scores, chunks))
            indexed.sort(key=lambda x: x[0], reverse=True)
            return [c for _, c in indexed[:top_k]]
        except Exception as e:
            logger.warning("Cross-encoder rerank failed: %s, fallback to text_similarity", e)
            return await self._rerank_text_similarity(query, chunks, top_k)

    def _text_score(self, query: str, chunk: str) -> float:
        """Простая оценка по совпадению слов и длине (без внешних моделей)."""
        q_lower = query.lower().strip()
        c_lower = chunk.lower()
        q_words = set(re.findall(r"\w+", q_lower))
        if not q_words:
            return 0.0
        matches = sum(1 for w in q_words if w in c_lower)
        return matches / len(q_words) if q_words else 0.0

    async def _rerank_text_similarity(
        self, query: str, chunks: List[str], top_k: int
    ) -> List[str]:
        """Реранкинг по текстовому сходству (быстро, без тяжёлых моделей)."""
        scored = [(self._text_score(query, c), c) for c in chunks]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    async def _rerank_hybrid(
        self, query: str, chunks: List[str], top_k: int
    ) -> List[str]:
        """Гибрид: сначала text_similarity отбирает кандидатов, затем cross_encoder (если есть)."""
        # Сначала отбираем больше кандидатов текстовым методом
        candidates = await self._rerank_text_similarity(query, chunks, min(top_k * 2, len(chunks)))
        if self._cross_encoder and len(candidates) > top_k:
            return await self._rerank_cross_encoder(query, candidates, top_k)
        return candidates[:top_k]
