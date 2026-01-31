"""
Предзагрузка эмбеддингов для частых запросов RAG-light (Фаза 3, день 3–4).
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Set
from datetime import datetime

logger = logging.getLogger(__name__)


class RAGLightPrefetch:
    """Предзагрузка эмбеддингов для частых запросов."""

    def __init__(
        self,
        embedding_batch_processor: Any,
        prefetch_file: str | None = None,
    ):
        self.embedding_batch_processor = embedding_batch_processor
        self.prefetch_file = prefetch_file
        self.prefetched_queries: Set[str] = set()
        self.stats: Dict[str, Any] = {
            "total_prefetched": 0,
            "last_prefetch_time": None,
            "prefetch_errors": 0,
        }

    async def load_frequent_queries(self, max_queries: int = 100) -> None:
        """Загрузка и предзагрузка частых запросов."""
        queries = await self._get_frequent_queries(max_queries)
        if not queries:
            logger.warning("No frequent queries to prefetch")
            return
        logger.info("Starting prefetch for %s queries", len(queries))
        batch_size = 20
        for i in range(0, len(queries), batch_size):
            batch = queries[i : i + batch_size]
            tasks = [
                self.embedding_batch_processor.get_embedding(q) for q in batch
            ]
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for q, r in zip(batch, results):
                    if isinstance(r, list):
                        self.prefetched_queries.add(q.strip().lower())
                    else:
                        self.stats["prefetch_errors"] += 1
            except Exception as e:
                logger.error("Error in prefetch batch: %s", e)
        self.stats["total_prefetched"] = len(self.prefetched_queries)
        self.stats["last_prefetch_time"] = datetime.now().isoformat()
        logger.info("Prefetch completed: %s queries cached", len(self.prefetched_queries))

    async def _get_frequent_queries(self, max_queries: int) -> List[str]:
        """Получение списка частых запросов."""
        queries: List[str] = []
        if self.prefetch_file and Path(self.prefetch_file).exists():
            try:
                with open(self.prefetch_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        queries = data[:max_queries]
                    elif isinstance(data, dict) and "queries" in data:
                        queries = data["queries"][:max_queries]
                logger.info("Loaded %s queries from %s", len(queries), self.prefetch_file)
            except Exception as e:
                logger.error("Error loading prefetch file: %s", e)
        if not queries:
            queries = self._get_default_queries()[:max_queries]
            logger.info("Using default queries: %s items", len(queries))
        seen: Set[str] = set()
        unique: List[str] = []
        for q in queries:
            if isinstance(q, str) and q.strip() and q.strip() not in seen:
                seen.add(q.strip())
                unique.append(q.strip())
        return unique[:max_queries]

    def _get_default_queries(self) -> List[str]:
        """Дефолтный список частых запросов."""
        return [
            "сколько стоит подписка",
            "как создать аккаунт",
            "время работы поддержки",
            "документация API",
            "как сбросить пароль",
            "тарифы и цены",
            "контакты поддержки",
            "как отменить подписку",
            "справка по использованию",
            "часто задаваемые вопросы",
            "как установить приложение",
            "требования к системе",
            "инструкция по настройке",
            "пробный период",
            "способы оплаты",
            "как обновить версию",
            "поддержка пользователей",
            "устранение неполадок",
            "база знаний",
            "форум сообщества",
        ]

    def is_prefetched(self, query: str) -> bool:
        """Проверка, предзагружен ли запрос."""
        return query.strip().lower() in self.prefetched_queries

    def get_stats(self) -> Dict[str, Any]:
        """Статистика предзагрузки."""
        return {
            **self.stats,
            "prefetched_queries_count": len(self.prefetched_queries),
            "prefetched_queries_sample": list(self.prefetched_queries)[:5]
            if self.prefetched_queries
            else [],
        }
