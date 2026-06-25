import logging
import os
from typing import Any, Dict, List

try:
    from sentence_transformers import CrossEncoder

    HAS_CROSS_ENCODER = True
except ImportError:
    HAS_CROSS_ENCODER = False

logger = logging.getLogger(__name__)


class RAGReranker:
    """
    RAG Reranker (Singularity 23.3):
    Использует Cross-Encoder для семантического переранжирования результатов RAG.
    Повышает точность выбора наиболее релевантных узлов знаний.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self.model = None
        self._load_attempted = False

    def _ensure_model(self) -> None:
        """Ленивая загрузка: не блокировать первый RAG-запрос скачиванием HF в __init__."""
        if self.model is not None or self._load_attempted:
            return
        self._load_attempted = True
        if os.getenv("RAG_RERANKER_ENABLED", "true").lower() in ("false", "0", "no"):
            logger.info("[RERANKER] Отключён (RAG_RERANKER_ENABLED=false)")
            return
        if not HAS_CROSS_ENCODER:
            return
        try:
            self.model = CrossEncoder(self.model_name, device="cpu")
            logger.info("✅ [RERANKER] Модель %s загружена", self.model_name)
        except Exception as e:
            logger.error("❌ [RERANKER] Ошибка загрузки модели %s: %s", self.model_name, e)

    def rerank(
        self, query: str, nodes: List[Dict[str, Any]], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Переранжирует список узлов на основе семантической близости к запросу.
        """
        self._ensure_model()
        if not self.model or not nodes:
            return nodes[:top_k]

        try:
            # Формируем пары (запрос, текст_узла)
            pairs = [[query, node.get("content", "")] for node in nodes]

            # Получаем оценки релевантности
            scores = self.model.predict(pairs)

            # Присваиваем оценки узлам
            for i, node in enumerate(nodes):
                node["rerank_score"] = float(scores[i])

            # Сортируем по убыванию оценки
            reranked_nodes = sorted(nodes, key=lambda x: x["rerank_score"], reverse=True)

            logger.info(
                f"🎯 [RERANKER] Переранжировано {len(nodes)} узлов, top-1 score: {reranked_nodes[0]['rerank_score']:.2f}"
            )
            return reranked_nodes[:top_k]

        except Exception as e:
            logger.error(f"❌ [RERANKER] Ошибка переранжирования: {e}")
            return nodes[:top_k]


_reranker = None


def get_rag_reranker():
    global _reranker
    if _reranker is None:
        _reranker = RAGReranker()
    return _reranker
