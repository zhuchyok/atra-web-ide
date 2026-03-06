"""
Semantic AICache Module.
Provides semantic caching for AI agent responses using PostgreSQL vector storage.
"""

import asyncio
import json
import logging
import os
from typing import Any, Optional, Union

# Third-party imports with fallbacks
try:
    import asyncpg  # type: ignore
except ImportError:
    asyncpg = None  # type: ignore

import httpx

try:
    from http_client import get_http_client
except ImportError:
    get_http_client = None
try:
    from json_fast import loads as _json_loads
except ImportError:
    _json_loads = None

logger = logging.getLogger(__name__)

# Единая локальная БД (в Docker задаётся DATABASE_URL через compose)
_DEFAULT_DB = "postgresql://admin:secret@localhost:5432/knowledge_os"
DATABASE_URL = os.getenv("DATABASE_URL") or _DEFAULT_DB
DB_URL_PRIMARY = DATABASE_URL
DB_URL_FALLBACK = DATABASE_URL

# Ollama embeddings: в Docker localhost недоступен — используем host.docker.internal
_is_docker = (
    os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
)
_default_embed_base = (
    "http://host.docker.internal:11434" if _is_docker else "http://localhost:11434"
)
_embed_base = os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_API_URL") or _default_embed_base
OLLAMA_EMBED_URL = os.getenv("OLLAMA_EMBED_URL") or f"{_embed_base.rstrip('/')}/api/embeddings"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "nomic-embed-text")  # Dedicated embedding model
# nomic-embed-text (v1/v1.5) output dimension; БД и кэш должны совпадать (миграция fix_embedding_dimensions_768)
EMBEDDING_DIM = 768
CACHE_THRESHOLD = 0.92  # Similarity threshold to return cached result
STRATEGIC_CACHE_THRESHOLD = 0.95  # Более строгий threshold для стратегических вопросов

# Ключевые слова стратегических вопросов (для высокого приоритета кэширования)
STRATEGIC_KEYWORDS = [
    "архитектур",
    "микросервис",
    "структур",
    "приоритет",
    "стратег",
    "планиро",
    "рефактор",
    "бюджет",
    "срок",
    "качество",
    "скорость",
    "стоит ли",
    "нужно ли",
    "совет",
    "директор",
    "okr",
    "цел",
    "задач",
]


async def get_embedding(text: str) -> Optional[list]:
    """
    Get embedding from Ollama. Uses shared HTTP client (connection reuse).
    При недоступности общего клиента — fallback на разовый AsyncClient (resilience).
    Внедрена логика повторных попыток (retries) для стабильности на Mac Studio.
    """
    max_retries = 3
    for attempt in range(max_retries):
        client = None
        if get_http_client:
            try:
                client = await get_http_client()
            except Exception as exc:
                logger.debug("Shared HTTP client unavailable, attempt %d: %s", attempt + 1, exc)

        try:
            if client is None:
                async with httpx.AsyncClient() as fallback_client:
                    res = await _do_embed_request(fallback_client, text)
            else:
                res = await _do_embed_request(client, text)

            if res:
                return res

            # Если вернулось None (например, 503), пробуем еще раз
            if attempt < max_retries - 1:
                await asyncio.sleep(2**attempt)

        except Exception as exc:
            if attempt < max_retries - 1:
                logger.warning("Embedding attempt %d failed: %s. Retrying...", attempt + 1, exc)
                await asyncio.sleep(2**attempt)
            else:
                logger.error("Embedding error after %d attempts (Ollama): %s", max_retries, exc)

    return None


async def _do_embed_request(client: httpx.AsyncClient, text: str) -> Optional[list]:
    """Single embedding request (shared or ad-hoc client)."""
    try:
        response = await client.post(
            OLLAMA_EMBED_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": text,
                "keep_alive": 0,
            },  # выгрузить сразу (MODEL_UNLOADING_AND_MEMORY)
            timeout=30.0,  # Увеличено с 10.0 до 30.0 для стабильности на Mac Studio
        )
        if response.status_code == 503:
            logger.warning("Ollama embeddings service unavailable (503). Skipping embedding.")
            return None
        response.raise_for_status()
        raw = response.content
        if not raw:
            logger.warning("Embedding response empty")
            return None
        data = _json_loads(raw) if _json_loads else response.json()
        if not isinstance(data, dict):
            return None
        return data.get("embedding")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Embedding error (Ollama): %s", exc)
        return None


class SemanticAICache:
    """
    Handles semantic caching of agent interactions using vector similarity.
    """

    def __init__(self, db_url: Optional[str] = None):
        """Initialize cache. Uses DATABASE_URL (local DB on Mac Studio) so cache and dashboard share one DB."""
        primary = db_url or DATABASE_URL or DB_URL_PRIMARY
        self.db_url_remote = primary  # основной URL (локальная БД)
        self.db_url_local = db_url or DATABASE_URL or DB_URL_FALLBACK
        self._embedding_cache = {}  # In-memory кэш эмбеддингов (legacy, для обратной совместимости)
        self._cache_size = 500  # Максимум эмбеддингов в кэше

        # Используем EmbeddingOptimizer, если доступен
        try:
            from embedding_optimizer import get_embedding_optimizer

            self._embedding_optimizer = get_embedding_optimizer(db_url=db_url or DB_URL_FALLBACK)
        except ImportError:
            self._embedding_optimizer = None

    async def _get_conn(self):
        """Connect to DB. Uses same DATABASE_URL as app when set, so cache and dashboard share one DB."""
        if not asyncpg:
            logger.error("asyncpg is not installed. Database connection unavailable.")
            return None, None

        # Подключение к локальной БД (Mac Studio)
        try:
            conn = await asyncio.wait_for(asyncpg.connect(self.db_url_remote), timeout=3.0)
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'semantic_ai_cache')"
            )
            if exists:
                return conn, "remote"
            await conn.close()
            logger.debug("Table 'semantic_ai_cache' not found on primary DB, trying fallback.")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.debug("Primary DB connection failed: %s", exc)

        # Fallback на local (или второй URL)
        if self.db_url_local == self.db_url_remote:
            return None, None
        try:
            conn = await asyncpg.connect(self.db_url_local)
            return conn, "local"
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("❌ DB connection failed: %s", exc)
            return None, None

    async def _get_cached_embedding(self, text: str) -> Optional[list]:
        """Получает эмбеддинг из кэша или вычисляет (с оптимизацией)"""
        # Используем EmbeddingOptimizer, если доступен
        if self._embedding_optimizer:
            cached = await self._embedding_optimizer.get_cached_embedding(text)
            if cached:
                return cached

            # Вычисляем эмбеддинг
            embedding = await get_embedding(text)
            if embedding:
                await self._embedding_optimizer.save_embedding(text, embedding)
            return embedding

        # Fallback на старую логику (для обратной совместимости); ключ = хэш нормализованного текста
        try:
            # Попытка импорта из cache_normalizer (может быть в другом месте или отсутствовать)
            # Используем Any для подавления ошибок типизации при динамическом импорте
            _rust_nh: Any = None
            try:
                from cache_normalizer import normalize_and_hash as _rn  # type: ignore

                _rust_nh = _rn
            except ImportError:
                # Попытка найти в текущем пакете или соседних
                try:
                    from .cache_normalizer import normalize_and_hash as _rn_local  # type: ignore

                    _rust_nh = _rn_local
                except ImportError:
                    raise ImportError("cache_normalizer not found")

            if _rust_nh is None:
                raise ImportError("normalize_and_hash not found")
            text_hash = _rust_nh(text)
        except ImportError:
            import hashlib

            normalized = " ".join(text.lower().split())
            text_hash = hashlib.md5(normalized.encode()).hexdigest()

        if text_hash in self._embedding_cache:
            return self._embedding_cache[text_hash]

        # Вычисляем эмбеддинг
        embedding = await get_embedding(text)
        if embedding:
            # Сохраняем в кэш
            if len(self._embedding_cache) >= self._cache_size:
                # Удаляем старые (FIFO)
                oldest_key = next(iter(self._embedding_cache))
                del self._embedding_cache[oldest_key]
            self._embedding_cache[text_hash] = embedding

        return embedding

    async def get_cache_info(self, query: str) -> Optional[dict[str, Any]]:
        """[SINGULARITY 10.0+] Получает расширенную информацию из кэша для префетчинга."""
        embedding = await self._get_cached_embedding(query)
        if not embedding:
            return None

        conn, _ = await self._get_conn()
        if not conn:
            return None

        try:
            # Ищем не только точное совпадение, но и семантически близкие темы для префетчинга
            rows = await conn.fetch(
                """
                SELECT query_text, expert_name, (1 - (embedding <=> $1::vector)) as similarity, metadata
                FROM semantic_ai_cache
                WHERE (1 - (embedding <=> $1::vector)) >= 0.85
                ORDER BY similarity DESC
                LIMIT 5
            """,
                str(embedding),
            )

            if not rows:
                if conn:
                    await conn.close()
                return None

            result: dict[str, Any] = {
                "knowledge_node_ids": [],
                "related_queries": [r["query_text"] for r in rows[1:]],
                "top_similarity": rows[0]["similarity"],
            }

            # Извлекаем ID узлов знаний из метаданных, если они там есть
            for r in rows:
                meta = r.get("metadata")
                if meta:
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except:
                            meta = {}
                    ids = meta.get("knowledge_node_ids", [])
                    if ids:
                        result["knowledge_node_ids"].extend(ids)

            await conn.close()
            return result
        except Exception as e:
            logger.error(f"Error in get_cache_info: {e}")
            return None

    async def prefetch_related_context(self, query: str):
        """[SINGULARITY 10.0+] Предиктивный префетчинг контекста на основе текущего запроса."""
        try:
            # 1. Анализируем текущий запрос и ищем связанные темы в кэше
            cache_info = await self.get_cache_info(query)
            if not cache_info or not cache_info.get("related_queries"):
                return

            # 2. Для каждой связанной темы подгружаем GraphRAG контекст в Redis
            from app.graphrag.graphrag_service import get_graphrag_service

            graphrag = get_graphrag_service()

            for related_query in cache_info["related_queries"][:3]:  # Увеличиваем до топ-3
                # Запускаем фоновую задачу префетчинга
                asyncio.create_task(graphrag.retrieve_graph_context(related_query))
                logger.info(f"🔮 [PREFETCH] Warm-up GraphRAG for: {related_query[:50]}...")

            # 3. [SINGULARITY 10.0+] Подгружаем связанные узлы знаний напрямую
            if cache_info.get("knowledge_node_ids"):
                from app.redis_manager import redis_manager

                # [SINGULARITY 21.3] Предиктивный прогрев Redis для связанных узлов
                for node_id in cache_info["knowledge_node_ids"][:10]:
                    # Фоновая задача на подгрузку контента узла в Redis
                    asyncio.create_task(self._warmup_node_to_redis(node_id))

                logger.info(
                    f"🔮 [PREFETCH] Warming up {len(cache_info['knowledge_node_ids'])} specific knowledge nodes."
                )

        except Exception as e:
            logger.debug(f"Prefetching failed: {e}")

    async def _warmup_node_to_redis(self, node_id: str):
        """Вспомогательный метод для прогрева конкретного узла в Redis."""
        try:
            from app.redis_manager import redis_manager

            conn, _ = await self._get_conn()
            if not conn:
                return

            content = await conn.fetchval(
                "SELECT content FROM knowledge_nodes WHERE id = $1", node_id
            )
            await conn.close()

            if content:
                await redis_manager.set_cache(f"node:{node_id}", content, ttl=3600)
        except Exception:
            pass

    async def get_cached_response(self, query: str, expert_name: str) -> Optional[str]:
        """Try to find a similar query in the semantic cache."""
        # Определяем, является ли это стратегическим вопросом
        is_strategic = any(keyword in query.lower() for keyword in STRATEGIC_KEYWORDS)

        # Используем кэш эмбеддингов для ускорения
        embedding = await self._get_cached_embedding(query)
        if not embedding:
            return None

        conn, source = await self._get_conn()
        if not conn:
            return None

        try:
            # Используем более строгий threshold для стратегических вопросов
            threshold = STRATEGIC_CACHE_THRESHOLD if is_strategic else CACHE_THRESHOLD
            # Для не-стратегических - более агрессивное кэширование
            aggressive_threshold = threshold if is_strategic else max(CACHE_THRESHOLD - 0.05, 0.75)

            logger.debug(
                f"🔍 [CACHE] Поиск в кэше: expert={expert_name}, "
                f"strategic={is_strategic}, threshold={aggressive_threshold:.2f}"
            )

            # Проверяем наличие колонок TTL (для обратной совместимости)
            has_ttl = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'semantic_ai_cache'
                    AND column_name = 'expires_at'
                )
            """)

            # SQL запрос с учетом TTL, если колонка существует
            if has_ttl:
                row = await conn.fetchrow(
                    """
                    SELECT response_text, (1 - (embedding <=> $1::vector)) as similarity
                    FROM semantic_ai_cache
                    WHERE expert_name = $2
                    AND (1 - (embedding <=> $1::vector)) >= $3
                    AND (expires_at IS NULL OR expires_at > NOW())
                    ORDER BY similarity DESC, last_used_at DESC
                    LIMIT 1
                """,
                    str(embedding),
                    expert_name,
                    aggressive_threshold,
                )
            else:
                row = await conn.fetchrow(
                    """
                    SELECT response_text, (1 - (embedding <=> $1::vector)) as similarity
                    FROM semantic_ai_cache
                    WHERE expert_name = $2
                    AND (1 - (embedding <=> $1::vector)) >= $3
                    ORDER BY similarity DESC, last_used_at DESC
                    LIMIT 1
                """,
                    str(embedding),
                    expert_name,
                    aggressive_threshold,
                )

            if row and row["similarity"] >= aggressive_threshold:
                # Update usage count
                await conn.execute(
                    """
                    UPDATE semantic_ai_cache
                    SET usage_count = usage_count + 1,
                        last_used_at = NOW()
                    WHERE query_text = $1 AND expert_name = $2
                """,
                    query,
                    expert_name,
                )
                await conn.close()
                if source == "local":
                    logger.info("🛡️ [OFFLINE CACHE HIT]")
                return row["response_text"]

            await conn.close()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Semantic cache error (%s): %s", source, exc)
        return None

    async def save_to_cache(
        self,
        query: str,
        response: str,
        expert_name: str,
        routing_source: Optional[str] = None,
        performance_score: Optional[float] = None,
        tokens_saved: int = 0,
        priority: str = "medium",
        ttl_seconds: Optional[int] = None,
    ):
        """Save a new interaction to the semantic cache with routing metrics."""
        embedding = await get_embedding(query)
        if not embedding:
            return
        if len(embedding) != EMBEDDING_DIM:
            logger.warning(
                "Save to cache skipped: embedding dimension %s != %s (OLLAMA_MODEL=%s). Run migration fix_embedding_dimensions_768.sql and use nomic-embed-text.",
                len(embedding),
                EMBEDDING_DIM,
                OLLAMA_MODEL,
            )
            return

        conn, source = await self._get_conn()
        if not conn:
            return

        try:
            # Определяем TTL на основе приоритета, если не указан
            if ttl_seconds is None:
                priority_ttl = {
                    "critical": 7 * 24 * 3600,  # 7 дней
                    "high": 3 * 24 * 3600,  # 3 дня
                    "medium": 24 * 3600,  # 1 день
                    "low": 6 * 3600,  # 6 часов
                }
                ttl_seconds = priority_ttl.get(priority, 24 * 3600)

            # Проверяем наличие колонок (для обратной совместимости)
            has_routing = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'semantic_ai_cache'
                    AND column_name = 'routing_source'
                )
            """)
            has_ttl = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'semantic_ai_cache'
                    AND column_name = 'ttl_seconds'
                )
            """)

            if has_routing and has_ttl:
                # Полная версия с TTL и приоритетами
                await conn.execute(
                    """
                    INSERT INTO semantic_ai_cache
                    (query_text, response_text, embedding, expert_name, routing_source, performance_score, tokens_saved, priority, ttl_seconds)
                    VALUES ($1, $2, $3::vector, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (query_text, expert_name) DO UPDATE
                    SET response_text = EXCLUDED.response_text,
                        embedding = EXCLUDED.embedding,
                        routing_source = EXCLUDED.routing_source,
                        performance_score = EXCLUDED.performance_score,
                        tokens_saved = EXCLUDED.tokens_saved,
                        priority = EXCLUDED.priority,
                        ttl_seconds = EXCLUDED.ttl_seconds,
                        expires_at = CURRENT_TIMESTAMP + INTERVAL '1 second' * EXCLUDED.ttl_seconds,
                        last_used_at = NOW()
                """,
                    query,
                    response,
                    str(embedding),
                    expert_name,
                    routing_source,
                    performance_score,
                    tokens_saved,
                    priority,
                    ttl_seconds,
                )
            elif has_routing:
                # Версия без TTL (старая схема)
                await conn.execute(
                    """
                    INSERT INTO semantic_ai_cache
                    (query_text, response_text, embedding, expert_name, routing_source, performance_score, tokens_saved)
                    VALUES ($1, $2, $3::vector, $4, $5, $6, $7)
                    ON CONFLICT (query_text, expert_name) DO UPDATE
                    SET response_text = EXCLUDED.response_text,
                        embedding = EXCLUDED.embedding,
                        routing_source = EXCLUDED.routing_source,
                        performance_score = EXCLUDED.performance_score,
                        tokens_saved = EXCLUDED.tokens_saved,
                        last_used_at = NOW()
                """,
                    query,
                    response,
                    str(embedding),
                    expert_name,
                    routing_source,
                    performance_score,
                    tokens_saved,
                )
            else:
                # Fallback for old schema
                await conn.execute(
                    """
                    INSERT INTO semantic_ai_cache (query_text, response_text, embedding, expert_name)
                    VALUES ($1, $2, $3::vector, $4)
                    ON CONFLICT (query_text, expert_name) DO UPDATE
                    SET response_text = EXCLUDED.response_text,
                        embedding = EXCLUDED.embedding,
                        last_used_at = NOW()
                """,
                    query,
                    response,
                    str(embedding),
                    expert_name,
                )

            await conn.close()
            if source == "local":
                logger.info("💾 Saved to local cache (Offline Mode)")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Save to cache error (%s): %s", source, exc)


async def test_cache():
    """Simple test function for the semantic cache."""
    cache = SemanticAICache()
    question = "Как уменьшить потребление токенов?"
    answer = "Для уменьшения потребления токенов используйте локальное кэширование."
    await cache.save_to_cache(question, answer, "Виктория")
    cached = await cache.get_cached_response(question, "Виктория")
    print(f"Cached result: {cached}")


if __name__ == "__main__":
    asyncio.run(test_cache())
