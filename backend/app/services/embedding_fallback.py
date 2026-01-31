"""
Fallback стратегии для эмбеддингов при недоступности Ollama (Фаза 3, день 3–4).
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SENTENCE_TRANSFORMERS_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer  # noqa: F401
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    logger.debug("sentence-transformers not available, local embedding fallback disabled")


class EmbeddingFallback:
    """Fallback стратегии для эмбеддингов при недоступности Ollama."""

    def __init__(
        self,
        local_model_name: str = "all-MiniLM-L6-v2",
        keyword_fallback_enabled: bool = True,
    ):
        self.local_model_name = local_model_name
        self.keyword_fallback_enabled = keyword_fallback_enabled
        self._local_model: Any = None  # Ленивая загрузка — не грузим при старте (latency)

    def _ensure_model(self) -> bool:
        """Ленивая загрузка sentence-transformers только при первом использовании."""
        if self._local_model is not None:
            return True
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.debug("sentence-transformers not installed, using keyword fallback only")
            return False
        try:
            self._local_model = SentenceTransformer(self.local_model_name)
            logger.info("Local embedding model loaded (lazy): %s", self.local_model_name)
            return True
        except Exception as e:
            logger.warning("Failed to load local model: %s", e)
            return False

    def get_local_embedding(self, text: str) -> Optional[List[float]]:
        """Получение эмбеддинга через локальную модель."""
        if not self._ensure_model():
            return None
        try:
            embedding = self._local_model.encode(text).tolist()
            logger.debug("Local embedding generated for: %s...", text[:50])
            return embedding
        except Exception as e:
            logger.error("Error generating local embedding: %s", e)
            return None

    async def keyword_search_fallback(
        self, query: str, knowledge_os: Any
    ) -> Optional[str]:
        """Fallback на keyword-поиск, если векторный недоступен."""
        if not self.keyword_fallback_enabled or not knowledge_os:
            return None
        try:
            rows = await knowledge_os.search_knowledge(query, limit=1)
            if rows:
                content = rows[0].get("content") or ""
                if content:
                    return content
        except Exception as e:
            logger.warning("Keyword fallback error: %s", e)
        return None

    def hybrid_search(
        self,
        query: str,
        vector_results: List[Tuple[str, float]],
        keyword_results: List[Tuple[str, float]],
        vector_weight: float = 0.7,
    ) -> List[Tuple[str, float]]:
        """Гибридный поиск: комбинирует векторные и keyword результаты."""
        combined: Dict[str, float] = {}
        if vector_results:
            max_v = max(s for _, s in vector_results) or 1.0
            for content, score in vector_results:
                combined[content] = (score / max_v) * vector_weight
        if keyword_results:
            max_k = max(s for _, s in keyword_results) or 1.0
            kw_weight = 1.0 - vector_weight
            for content, score in keyword_results:
                norm = score / max_k
                combined[content] = combined.get(content, 0) + norm * kw_weight
        return sorted(combined.items(), key=lambda x: x[1], reverse=True)

    def get_stats(self) -> Dict[str, Any]:
        """Статистика fallback."""
        return {
            "local_model_available": self._local_model is not None,
            "local_model_name": self.local_model_name if self._local_model else None,
            "keyword_fallback_enabled": self.keyword_fallback_enabled,
            "sentence_transformers_available": SENTENCE_TRANSFORMERS_AVAILABLE,
        }
