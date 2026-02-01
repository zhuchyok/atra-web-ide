"""
RAG-light: быстрый ответ на фактуальные вопросы из БЗ (Фаза 2).
Один чанк по вектору, высокий порог релевантности, таймаут 200 ms.
Эмбеддинги через Ollama (nomic-embed-text).
Фаза 3: батчинг эмбеддингов, предзагрузка, fallback на keyword-поиск.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def _rag_metrics_decorator(func):
    """Декоратор метрик RAG (ленивый импорт, без зависимости при старте)."""
    async def wrapper(self, query: str, timeout_ms: Optional[int] = None, user_id: Optional[str] = None):
        try:
            from app.metrics.prometheus_metrics import (
                RAG_REQUESTS,
                RAG_DURATION,
                RAG_CHUNKS_RETURNED,
            )
            import time
            RAG_REQUESTS.labels(mode="ask", type="rag_light", path="processing").inc()
            start = time.perf_counter()
            result = await func(self, query, timeout_ms, user_id)
            RAG_DURATION.labels(mode="ask", type="rag_light").observe(time.perf_counter() - start)
            if result is not None:
                RAG_CHUNKS_RETURNED.observe(1)
            return result
        except Exception:
            return await func(self, query, timeout_ms, user_id)
    return wrapper


class RAGLightService:
    """
    Быстрый RAG для фактуальных запросов:
    - Эмбеддинг запроса через Ollama (или батч/локальная модель)
    - Один чанк с высоким порогом релевантности (pgvector)
    - Краткий ответ из контекста, таймаут 200 ms
    - Фаза 3: EmbeddingBatchProcessor, RAGLightPrefetch, EmbeddingFallback
    """

    def __init__(
        self,
        knowledge_os=None,
        enabled: bool = True,
        similarity_threshold: float = 0.65,
        max_response_length: int = 150,
        timeout_ms: int = 200,
        ab_testing_service: Any = None,
        reranking_service: Any = None,
        query_rewriter_service: Any = None,
        config: Any = None,
    ):
        self.knowledge_os = knowledge_os
        self.enabled = enabled
        self.similarity_threshold = similarity_threshold
        self.max_response_length = max_response_length
        self.timeout_ms = timeout_ms
        self.ab_testing = ab_testing_service
        self.reranking_service = reranking_service
        self.query_rewriter_service = query_rewriter_service
        self.use_reranking = (
            config.get("reranking_enabled", False) if config else False
        )
        self.use_query_expansion = (
            config.get("query_expansion_enabled", True) if config else True
        )
        self.use_query_rewriter = (
            config.get("query_rewriter_enabled", True) if config else True
        )
        self._cache: dict = {}
        self._cache_max = 200
        self.rag_context_cache: Any = None
        self.embedding_batch_processor: Any = None
        self.prefetch_service: Any = None
        self.fallback_service: Any = None
        self._optimizations_inited = False

    def _init_optimizations(self) -> None:
        """Инициализация оптимизаций (Фаза 3, день 3–4)."""
        if self._optimizations_inited:
            return
        self._optimizations_inited = True
        settings = get_settings()
        if getattr(settings, "embedding_batch_enabled", False):
            try:
                from app.services.embedding_batch import EmbeddingBatchProcessor
                self.embedding_batch_processor = EmbeddingBatchProcessor(
                    ollama_url=settings.ollama_url,
                    ollama_model=getattr(settings, "ollama_embed_model", "nomic-embed-text"),
                    batch_size=getattr(settings, "embedding_batch_size", 10),
                    batch_timeout_ms=getattr(settings, "embedding_batch_timeout_ms", 50),
                )
            except Exception as e:
                logger.debug("EmbeddingBatchProcessor init skipped: %s", e)
        if getattr(settings, "rag_light_prefetch_enabled", False) and self.embedding_batch_processor:
            try:
                from app.services.rag_light_prefetch import RAGLightPrefetch
                self.prefetch_service = RAGLightPrefetch(
                    self.embedding_batch_processor,
                    prefetch_file=getattr(settings, "rag_light_prefetch_file", None),
                )
            except Exception as e:
                logger.debug("RAGLightPrefetch init skipped: %s", e)
        if getattr(settings, "embedding_fallback_enabled", False):
            try:
                from app.services.embedding_fallback import EmbeddingFallback
                self.fallback_service = EmbeddingFallback(
                    local_model_name=getattr(settings, "local_embedding_model", "all-MiniLM-L6-v2"),
                    keyword_fallback_enabled=getattr(settings, "keyword_fallback_enabled", True),
                )
            except Exception as e:
                logger.debug("EmbeddingFallback init skipped: %s", e)
        if getattr(settings, "rag_context_cache_enabled", True):
            try:
                from app.services.rag_context_cache import get_rag_context_cache
                ttl = getattr(settings, "rag_cache_ttl_sec", None) or getattr(settings, "rag_light_cache_ttl", 300)
                self.rag_context_cache = get_rag_context_cache(
                    ttl=ttl,
                    use_redis=bool(getattr(settings, "redis_url", None)),
                )
            except Exception as e:
                logger.debug("RAGContextCache init skipped: %s", e)

    async def _get_embedding_optimized(self, query: str) -> Optional[List[float]]:
        """
        Оптимизированное получение эмбеддинга.
        Порядок (для минимальной latency): батч-кэш → Ollama → MLX (если добавим) → fallback.
        Fallback (sentence-transformers) — последний, т.к. медленный (холодный старт ~5с).
        """
        self._init_optimizations()
        try:
            from app.metrics.prometheus_metrics import record_cache_hit
        except Exception:
            record_cache_hit = None

        # 1. Батч-кэш (Ollama под капотом, быстрые cache hits)
        if self.embedding_batch_processor:
            emb = await self.embedding_batch_processor.get_embedding(query)
            if emb:
                if record_cache_hit:
                    try:
                        record_cache_hit("embedding_batch")
                    except Exception:
                        pass
                return emb

        # 2. Ollama напрямую (быстро, без загрузки Python-модели)
        emb = await self.get_embedding(query)
        if emb:
            return emb

        # 3. Fallback: sentence-transformers (медленно, только если Ollama недоступна)
        if self.fallback_service:
            emb = self.fallback_service.get_local_embedding(query)
            if emb:
                if record_cache_hit:
                    try:
                        record_cache_hit("embedding")
                    except Exception:
                        pass
                logger.debug("Using local embedding fallback for: %s...", query[:50])
                return emb

        return None

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Получение эмбеддинга через Ollama API."""
        settings = get_settings()
        url = f"{settings.ollama_url.rstrip('/')}/api/embeddings"
        model = getattr(settings, "ollama_embed_model", "nomic-embed-text")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.post(
                    url,
                    json={"model": model, "prompt": text[:8000]},
                )
                if r.status_code != 200:
                    logger.warning("Ollama embeddings status %s: %s", r.status_code, r.text[:200])
                    return None
                data = r.json()
                return data.get("embedding")
        except Exception as e:
            logger.warning("RAG-light get_embedding error: %s", e)
            return None

    async def search_chunks(
        self,
        query: str,
        limit: int = 5,
        threshold: Optional[float] = None,
        user_id: Optional[str] = None,
    ) -> List[Tuple[str, float]]:
        """
        Поиск нескольких чанков по вектору (для реранкинга и валидации).
        Returns: [(content, similarity), ...]
        """
        if not self.enabled or not self.knowledge_os:
            return []
        th = threshold if threshold is not None else self.similarity_threshold

        if self.rag_context_cache:
            cached = await self.rag_context_cache.get_context(query, user_id, limit=limit, threshold=th)
            if cached:
                return cached

        search_query = await self._prepare_query_for_search(query)
        embedding = await self._get_embedding_optimized(search_query)
        if not embedding:
            return []
        rows = await self.knowledge_os.search_knowledge_by_vector(
            embedding,
            limit=limit,
            threshold=th,
        )
        result = [
            (r.get("content") or "", float(r.get("similarity", 0)))
            for r in rows
        ]
        if result and self.rag_context_cache:
            await self.rag_context_cache.save_context(query, result, user_id, limit=limit, threshold=th)
        return result

    async def search_with_reranking(
        self,
        query: str,
        embedding: Optional[List[float]] = None,
        limit: int = 5,
    ) -> List[str]:
        """
        Поиск с реранкингом: получаем больше чанков, реранжируем, возвращаем топ limit.
        """
        if not self.enabled or not self.knowledge_os:
            return []
        if embedding is None:
            embedding = await self._get_embedding_optimized(query)
        if not embedding:
            return []
        chunks = await self.search_chunks(
            query, limit=limit * 2, threshold=self.similarity_threshold
        )
        if not chunks:
            return []
        chunk_texts = [c[0] for c in chunks]
        if self.use_reranking and self.reranking_service:
            try:
                reranked = await self.reranking_service.rerank_chunks(
                    query, chunk_texts, method="hybrid", top_k=limit
                )
                return reranked[:limit]
            except Exception as e:
                logger.warning("Reranking failed: %s, using original order", e)
        return chunk_texts[:limit]

    async def get_chunks_for_query(self, query: str, limit: int = 5) -> List[str]:
        """
        Получение чанков для запроса (для валидации и оценки faithfulness).
        """
        chunks = await self.search_with_reranking(query, limit=limit)
        return chunks

    async def _prepare_query_for_search(self, query: str) -> str:
        """
        Подготовка запроса: переписывание (если включено) → расширение.
        QueryRewriter (эвристики) + query expansion для лучшего retrieval.
        """
        q = query
        if self.use_query_rewriter and self.query_rewriter_service and query:
            try:
                rewritten = await self.query_rewriter_service.rewrite_for_rag(query)
                if rewritten and rewritten.strip():
                    q = rewritten.strip()
                    if q != query:
                        logger.debug("Query rewritten: %s -> %s", query[:40], q[:60])
            except Exception as e:
                logger.debug("Query rewrite skipped: %s", e)
        return self._expand_query_for_search(q)

    def _expand_query_for_search(self, query: str) -> str:
        """Расширение запроса для улучшения retrieval (query expansion)."""
        if not self.use_query_expansion or not query:
            return query
        try:
            from app.services.query_expansion import expand_query, expand_query_fallback
            expanded = expand_query(query)
            if expanded == query:
                expanded = expand_query_fallback(query)
            if expanded != query:
                logger.debug("Query expanded: %s -> %s", query[:40], expanded[:60])
            return expanded
        except Exception as e:
            logger.debug("Query expansion skipped: %s", e)
            return query

    async def search_one_chunk(
        self, query: str, limit: int = 1, threshold: Optional[float] = None, user_id: Optional[str] = None
    ) -> Optional[Tuple[str, float]]:
        """
        Поиск одного наиболее релевантного чанка в БЗ по вектору.
        threshold: переопределение порога (для A/B тестов).
        Returns:
            (content, similarity) or None
        """
        if not self.enabled or not self.knowledge_os:
            return None
        th = threshold if threshold is not None else self.similarity_threshold

        if self.rag_context_cache:
            cached = await self.rag_context_cache.get_context(query, user_id, limit=1, threshold=th)
            if cached:
                return cached[0]

        search_query = await self._prepare_query_for_search(query)
        embedding = await self._get_embedding_optimized(search_query)
        if not embedding:
            return None
        rows = await self.knowledge_os.search_knowledge_by_vector(
            embedding,
            limit=limit,
            threshold=th,
        )
        if not rows:
            return None
        r = rows[0]
        content = r.get("content") or ""
        sim = float(r.get("similarity", 0))
        result = (content, sim)
        if self.rag_context_cache:
            await self.rag_context_cache.save_context(query, [result], user_id, limit=1, threshold=th)
        return result

    def extract_direct_answer(self, query: str, chunk: str) -> str:
        """
        Извлекает краткий ответ из чанка для запроса.
        Ищет предложения с ключевыми словами и фактами (числа, даты).
        """
        query_lower = query.lower()
        chunk_lower = chunk.lower()
        keywords = (
            "это", "составляет", "равно", "стоит", "находится", "является", "включает",
        )
        sentences = chunk.replace(".\n", ". ").split(". ")
        for sentence in sentences:
            s = sentence.strip()
            if not s:
                continue
            s_lower = s.lower()
            if any(w in s_lower for w in query_lower.split()[:3]):
                return self._truncate_response(s)
            if any(kw in s_lower for kw in keywords):
                if any(c.isdigit() for c in s):
                    return self._truncate_response(s)
        return self._truncate_response(chunk)

    def _truncate_response(self, text: str, max_length: Optional[int] = None) -> str:
        if max_length is None:
            max_length = self.max_response_length
        if len(text) <= max_length:
            out = text.strip()
        else:
            truncated = text[:max_length]
            last_space = truncated.rfind(" ")
            if last_space > max_length // 2:
                truncated = truncated[:last_space]
            out = truncated.strip() + "..."
        # Обеспечиваем точку в конце для coherence (короткие ответы без точки)
        if out and out[-1] not in ".!?":
            out = out + "."
        return out

    @_rag_metrics_decorator
    async def fast_fact_answer(
        self, query: str, timeout_ms: Optional[int] = None, user_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Основной метод: быстрый ответ на фактуальный вопрос из БЗ.
        user_id: для A/B тестов (порог similarity из эксперимента).
        Returns:
            str — ответ или None
        """
        if not self.enabled:
            return None
        timeout_ms = timeout_ms or self.timeout_ms
        threshold_override = None
        if self.ab_testing and user_id:
            try:
                threshold_override = self.ab_testing.get_experiment_parameter(
                    user_id, "rag_light_threshold", "threshold"
                )
            except Exception:
                pass
        cache_key = hash(query.strip().lower())
        if cache_key in self._cache:
            try:
                from app.metrics.prometheus_metrics import record_cache_hit
                record_cache_hit("rag_light_context")
            except Exception:
                pass
            return self._cache[cache_key]
        import time
        t0 = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                self._fast_fact_answer_impl(query, threshold=threshold_override),
                timeout=timeout_ms / 1000.0,
            )
            duration_ms = (time.perf_counter() - t0) * 1000
            if result and len(self._cache) < self._cache_max:
                self._cache[cache_key] = result
            if self.ab_testing and user_id:
                try:
                    self.ab_testing.track_event(
                        user_id, "rag_light_threshold", "success", 1.0 if result else 0.0
                    )
                    self.ab_testing.track_event(
                        user_id, "rag_light_threshold", "response_time_ms", duration_ms
                    )
                except Exception:
                    pass
            return result
        except asyncio.TimeoutError:
            logger.warning("RAG-light timeout for query: %s...", query[:50])
        except Exception as e:
            logger.error("RAG-light error: %s", e, exc_info=True)
        return None

    async def _fast_fact_answer_impl(
        self, query: str, threshold: Optional[float] = None
    ) -> Optional[str]:
        if self.use_reranking and self.reranking_service:
            chunks = await self.search_with_reranking(query, limit=3)
            if not chunks:
                self._init_optimizations()
                if self.fallback_service and self.knowledge_os:
                    chunk = await self.fallback_service.keyword_search_fallback(
                        query, self.knowledge_os
                    )
                    if chunk:
                        logger.info(
                            "RAG-light keyword fallback for: %s...", query[:50]
                        )
                        return self.extract_direct_answer(query, chunk)
                return None
            best_chunk = chunks[0]
            answer = self.extract_direct_answer(query, best_chunk)
            logger.info(
                "RAG-light success (reranked): query='%s...', answer_len=%s",
                query[:30],
                len(answer),
            )
            return answer

        res = await self.search_one_chunk(query, limit=1, threshold=threshold)
        if not res:
            self._init_optimizations()
            if self.fallback_service and self.knowledge_os:
                chunk = await self.fallback_service.keyword_search_fallback(
                    query, self.knowledge_os
                )
                if chunk:
                    logger.info("RAG-light keyword fallback for: %s...", query[:50])
                    return self.extract_direct_answer(query, chunk)
            return None
        chunk, similarity = res
        answer = self.extract_direct_answer(query, chunk)
        logger.info(
            "RAG-light success: query='%s...', similarity=%.2f, answer_len=%s",
            query[:30],
            similarity,
            len(answer),
        )
        return answer


_rag_light_service: Optional[RAGLightService] = None


def get_rag_light_service(knowledge_os=None) -> RAGLightService:
    """Возвращает синглтон RAG-light сервиса (настраивается из config)."""
    global _rag_light_service
    if _rag_light_service is None:
        settings = get_settings()
        enabled = getattr(settings, "rag_light_enabled", True)
        ab_testing = None
        try:
            from app.services.ab_testing import get_ab_testing_service
            ab_testing = get_ab_testing_service()
        except Exception:
            pass
        reranking_service = None
        query_rewriter_service = None
        config = {
            "query_expansion_enabled": getattr(settings, "query_expansion_enabled", True),
            "query_rewriter_enabled": getattr(settings, "query_rewriter_enabled", True),
        }
        if getattr(settings, "reranking_enabled", False):
            try:
                from app.services.reranking import RerankingService
                reranking_service = RerankingService(
                    method="text_similarity",
                    top_k=5,
                )
                config["reranking_enabled"] = True
            except Exception as e:
                logger.debug("RerankingService init skipped: %s", e)
        if getattr(settings, "query_rewriter_enabled", True):
            try:
                from app.services.query_rewriter import QueryRewriter
                query_rewriter_service = QueryRewriter(use_llm=False)
            except Exception as e:
                logger.debug("QueryRewriter init skipped: %s", e)
                config["query_rewriter_enabled"] = False
        _rag_light_service = RAGLightService(
            knowledge_os=knowledge_os,
            enabled=enabled,
            similarity_threshold=getattr(settings, "rag_light_threshold", 0.75),
            max_response_length=getattr(settings, "rag_light_max_length", 150),
            timeout_ms=getattr(settings, "rag_light_timeout_ms", 200),
            ab_testing_service=ab_testing,
            reranking_service=reranking_service,
            query_rewriter_service=query_rewriter_service,
            config=config,
        )
        _rag_light_service._init_optimizations()
    elif knowledge_os is not None and _rag_light_service.knowledge_os is None:
        _rag_light_service.knowledge_os = knowledge_os
    return _rag_light_service
