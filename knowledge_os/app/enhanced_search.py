"""
Enhanced Multimodal Search for Knowledge OS - FIXED
Улучшенный мультимодальный поиск с поддержкой разных типов запросов
"""

import asyncio
import json
import logging
import math
import os
import re
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

import asyncpg
import httpx
import redis.asyncio as redis

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
VECTOR_CORE_URL = "http://localhost:8001"

# [RERANKER v2] Lazy Cross-Encoder — only when RAG_RERANKER_ENABLED=true
_RERANKER_MODEL = None


def _reranker_enabled() -> bool:
    return os.getenv("RAG_RERANKER_ENABLED", "true").lower() in ("1", "true", "yes")


def get_reranker():
    global _RERANKER_MODEL
    if _RERANKER_MODEL is None:
        from sentence_transformers import CrossEncoder

        model_name = os.getenv("RAG_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        logger.info("📥 Loading Cross-Encoder: %s", model_name)
        _RERANKER_MODEL = CrossEncoder(model_name, max_length=512)
    return _RERANKER_MODEL


async def rerank_results(query: str, results: list[dict]) -> list[dict]:
    """Переранжирование результатов с помощью Cross-Encoder [RERANKER v2]."""
    if not results:
        return []
    if not _reranker_enabled():
        return results

    load_timeout = float(os.getenv("RAG_RERANKER_LOAD_TIMEOUT_SEC", "20"))
    predict_timeout = float(os.getenv("RAG_RERANKER_PREDICT_TIMEOUT_SEC", "15"))
    try:
        model = await asyncio.wait_for(asyncio.to_thread(get_reranker), timeout=load_timeout)
        pairs = [[query, (r.get("content") or "")[:2000]] for r in results]
        scores = await asyncio.wait_for(
            asyncio.to_thread(model.predict, pairs), timeout=predict_timeout
        )

        for i, result in enumerate(results):
            sig_score = 1 / (1 + math.exp(-float(scores[i])))
            result["rerank_score"] = float(scores[i])
            result["similarity"] = sig_score

        return sorted(results, key=lambda x: x["similarity"], reverse=True)
    except Exception as e:
        logger.warning("⚠️ Rerank skipped: %s", e)
        return results


class SearchMode(Enum):
    """Режимы поиска"""

    SEMANTIC = "semantic"  # Семантический (по умолчанию)
    KEYWORD = "keyword"  # По ключевым словам
    METRIC = "metric"  # По метрикам (числовые значения)
    TEMPORAL = "temporal"  # По временным меткам
    HYBRID = "hybrid"  # Гибридный (семантический + ключевые слова)


class QueryParams:
    """Helper to manage dynamic SQL parameters"""

    def __init__(self, initial_params: list[Any] = None):
        self.params = initial_params or []

    def add(self, value: Any) -> str:
        self.params.append(value)
        return f"${len(self.params)}"

    def get_all(self) -> list[Any]:
        return self.params


async def get_embedding(text: str) -> list[float]:
    """Получение эмбеддинга через Ollama [HYBRID v2]"""
    try:
        from app.semantic_cache import get_embedding as get_ollama_embedding

        emb = await get_ollama_embedding(text)
        if emb:
            return emb
    except Exception as e:
        print(f"⚠️ Ошибка получения эмбеддинга через semantic_cache: {e}")

    # Fallback на прямой запрос к Ollama если импорт не сработал
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()["embedding"]


def detect_search_mode(query: str) -> tuple[SearchMode, dict]:
    """Автоматическое определение режима поиска"""
    query_lower = query.lower()
    metadata = {}

    # Поиск по метрикам (числовые значения)
    metric_patterns = [
        r"\d+\.?\d*\s*(percent|%|процент)",
        r"\d+\.?\d*\s*(gb|mb|kb|bytes)",
        r"\d+\.?\d*\s*(ms|seconds|минут|часов)",
        r"(больше|меньше|>|<|>=|<=)\s*\d+",
        r"(score|confidence|similarity)\s*[><=]?\s*\d+",
    ]
    if any(re.search(pattern, query_lower) for pattern in metric_patterns):
        return SearchMode.METRIC, metadata

    # Поиск по времени
    temporal_patterns = [
        r"(сегодня|вчера|неделю|месяц|год)",
        r"\d{4}-\d{2}-\d{2}",  # Дата YYYY-MM-DD
        r"(last|recent|новые|последние)",
        r"(created|updated|created_at|updated_at)",
    ]
    if any(re.search(pattern, query_lower) for pattern in temporal_patterns):
        return SearchMode.TEMPORAL, metadata

    # Ключевые слова (точные совпадения)
    keyword_indicators = [
        "точное совпадение",
        "exact match",
        "keyword",
        "найди текст",
        "find text",
        "contains",
    ]
    if any(indicator in query_lower for indicator in keyword_indicators):
        return SearchMode.KEYWORD, metadata

    # Гибридный (если есть и семантические, и ключевые слова)
    if len(query.split()) > 5 and any(word.isalnum() and len(word) > 4 for word in query.split()):
        return SearchMode.HYBRID, metadata

    # По умолчанию - семантический
    return SearchMode.SEMANTIC, metadata


async def semantic_search(
    conn: asyncpg.Connection, query: str, domain: Optional[str] = None, limit: int = 5
) -> list[dict]:
    """Семантический поиск через эмбеддинги"""
    embedding = await get_embedding(query)
    qp = QueryParams([str(embedding)])

    sql = """
        SELECT id, content, confidence_score, usage_count,
               (1 - (embedding <=> $1::vector)) as similarity,
               created_at, domain_id
        FROM knowledge_nodes
        WHERE confidence_score > 0.3
        AND embedding IS NOT NULL
    """

    if domain:
        sql += f" AND domain_id = (SELECT id FROM domains WHERE name = {qp.add(domain)})"

    sql += f" ORDER BY similarity DESC LIMIT {qp.add(limit)}"

    results = await conn.fetch(sql, *qp.get_all())
    return [dict(r) for r in results]


async def keyword_search(
    conn: asyncpg.Connection, query: str, domain: Optional[str] = None, limit: int = 5
) -> list[dict]:
    """Поиск по ключевым словам (BM25/FTS) [HYBRID v2]"""
    qp = QueryParams()

    # Очищаем запрос для tsquery
    clean_query = re.sub(r"[^\w\s]", " ", query).strip()
    ts_query = " & ".join(clean_query.split())

    if not ts_query:
        return []

    sql = f"""
        SELECT id, content, confidence_score, usage_count,
               ts_rank_cd(content_tsvector, to_tsquery('russian', {qp.add(ts_query)})) as similarity,
               created_at, domain_id
        FROM knowledge_nodes
        WHERE confidence_score > 0.3
        AND content_tsvector @@ to_tsquery('russian', {qp.add(ts_query)})
    """

    if domain:
        sql += f" AND domain_id = (SELECT id FROM domains WHERE name = {qp.add(domain)})"

    sql += f" ORDER BY similarity DESC, usage_count DESC LIMIT {qp.add(limit)}"

    results = await conn.fetch(sql, *qp.get_all())
    return [dict(r) for r in results]


async def metric_search(
    conn: asyncpg.Connection, query: str, domain: Optional[str] = None, limit: int = 5
) -> list[dict]:
    """Поиск по метрикам (числовые значения)"""
    numbers = re.findall(r"\d+\.?\d*", query)
    qp = QueryParams()

    sql = """
        SELECT id, content, confidence_score, usage_count,
               confidence_score as similarity,
               created_at, domain_id,
               metadata
        FROM knowledge_nodes
        WHERE confidence_score > 0.3
    """

    conditions = []

    if numbers:
        try:
            threshold = float(numbers[0])
            if "больше" in query.lower() or ">" in query:
                conditions.append(f"confidence_score > {qp.add(threshold)}")
            elif "меньше" in query.lower() or "<" in query:
                conditions.append(f"confidence_score < {qp.add(threshold)}")
            else:
                conditions.append(f"confidence_score >= {qp.add(threshold)}")
        except ValueError:
            pass

    if "usage" in query.lower() or "использование" in query.lower():
        if numbers and len(numbers) > 1:
            try:
                usage_threshold = int(numbers[1])
                conditions.append(f"usage_count >= {qp.add(usage_threshold)}")
            except (ValueError, IndexError):
                pass

    if conditions:
        sql += " AND " + " AND ".join(conditions)

    if domain:
        sql += f" AND domain_id = (SELECT id FROM domains WHERE name = {qp.add(domain)})"

    sql += f" ORDER BY confidence_score DESC, usage_count DESC LIMIT {qp.add(limit)}"

    results = await conn.fetch(sql, *qp.get_all())
    return [dict(r) for r in results]


async def temporal_search(
    conn: asyncpg.Connection, query: str, domain: Optional[str] = None, limit: int = 5
) -> list[dict]:
    """Поиск по временным меткам"""
    query_lower = query.lower()
    qp = QueryParams()

    if "сегодня" in query_lower or "today" in query_lower:
        time_condition = "created_at >= CURRENT_DATE"
    elif "вчера" in query_lower or "yesterday" in query_lower:
        time_condition = (
            "created_at >= CURRENT_DATE - INTERVAL '1 day' AND created_at < CURRENT_DATE"
        )
    elif "неделю" in query_lower or "week" in query_lower:
        time_condition = "created_at >= NOW() - INTERVAL '7 days'"
    elif "месяц" in query_lower or "month" in query_lower:
        time_condition = "created_at >= NOW() - INTERVAL '30 days'"
    elif "год" in query_lower or "year" in query_lower:
        time_condition = "created_at >= NOW() - INTERVAL '365 days'"
    elif "новые" in query_lower or "recent" in query_lower or "последние" in query_lower:
        time_condition = "created_at >= NOW() - INTERVAL '24 hours'"
    else:
        time_condition = "created_at >= NOW() - INTERVAL '7 days'"

    sql = f"""
        SELECT id, content, confidence_score, usage_count,
               EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600 as hours_ago,
               1.0 - (EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400 / 30) as similarity,
               created_at, domain_id
        FROM knowledge_nodes
        WHERE confidence_score > 0.3
        AND {time_condition}
    """

    if domain:
        sql += f" AND domain_id = (SELECT id FROM domains WHERE name = {qp.add(domain)})"

    sql += f" ORDER BY created_at DESC LIMIT {qp.add(limit)}"

    results = await conn.fetch(sql, *qp.get_all())
    return [dict(r) for r in results]


async def hybrid_search(
    conn: asyncpg.Connection, query: str, domain: Optional[str] = None, limit: int = 5
) -> list[dict]:
    """Гибридный поиск: семантический + BM25 [HYBRID v2]"""
    # 1. Получаем результаты из обоих источников
    semantic_results = await semantic_search(conn, query, domain, limit * 3)
    keyword_results = await keyword_search(conn, query, domain, limit * 3)

    combined = {}

    # 2. Нормализуем веса (Reciprocal Rank Fusion или взвешенная сумма)
    # Используем взвешенную сумму: 0.7 Vector + 0.3 BM25

    for result in semantic_results:
        node_id = str(result["id"])
        similarity = float(result.get("similarity", 0))
        if node_id not in combined:
            combined[node_id] = result.copy()
            combined[node_id]["vector_score"] = similarity
            combined[node_id]["keyword_score"] = 0.0
        else:
            combined[node_id]["vector_score"] = similarity

    for result in keyword_results:
        node_id = str(result["id"])
        similarity = float(result.get("similarity", 0))
        if node_id not in combined:
            combined[node_id] = result.copy()
            combined[node_id]["keyword_score"] = similarity
            combined[node_id]["vector_score"] = 0.0
        else:
            combined[node_id]["keyword_score"] = similarity

    # 3. Финальный скоринг
    for node_id in combined:
        v = combined[node_id].get("vector_score", 0)
        k = combined[node_id].get("keyword_score", 0)
        # Нормализация BM25 (ts_rank может быть > 1)
        k_norm = min(1.0, k)
        combined[node_id]["similarity"] = (v * 0.7) + (k_norm * 0.3)

    sorted_results = sorted(combined.values(), key=lambda x: x.get("similarity", 0), reverse=True)

    # 4. Cross-Encoder Re-ranking [RERANKER v2] — only if enabled
    candidates = sorted_results[:15]
    if _reranker_enabled() and len(candidates) > 1:
        logger.info("🔍 [RERANKER] Re-ranking %s candidates...", len(candidates))
        reranked = await rerank_results(query, candidates)
        final_results = reranked + sorted_results[15:]
        return final_results[:limit]

    return sorted_results[:limit]


async def enhanced_search_knowledge(
    query: str,
    domain: Optional[str] = None,
    mode: Optional[SearchMode] = None,
    limit: int = 5,
    use_cache: bool = True,
) -> dict:
    """Улучшенный мультимодальный поиск"""
    if mode is None:
        mode, metadata = detect_search_mode(query)
    else:
        metadata = {}

    if use_cache:
        try:
            # План «ракетная скорость» п.2.2: многоуровневый кэш (In-memory + Redis)
            import hashlib

            query_hash = hashlib.md5(
                f"{mode.value}:{query}:{domain or 'global'}".encode()
            ).hexdigest()

            # 1. In-memory cache (самый быстрый)
            if not hasattr(enhanced_search_knowledge, "_mem_cache"):
                enhanced_search_knowledge._mem_cache = {}

            if query_hash in enhanced_search_knowledge._mem_cache:
                cached_entry = enhanced_search_knowledge._mem_cache[query_hash]
                if (datetime.now() - cached_entry["ts"]).total_seconds() < 300:  # 5 минут in-memory
                    print(f"🚀 [MEM CACHE HIT] {mode.value} search: {query}")
                    return cached_entry["data"]

            # 2. Redis cache
            rd = redis.from_url(REDIS_URL, decode_responses=True)
            cache_key = f"search:{mode.value}:{query}:{domain or 'global'}"
            cached_data = await rd.get(cache_key)
            if cached_data:
                data = json.loads(cached_data)
                print(f"⚡ [REDIS CACHE HIT] {mode.value} search: {query}")
                # Обновляем in-memory кэш
                enhanced_search_knowledge._mem_cache[query_hash] = {
                    "data": data,
                    "ts": datetime.now(),
                }
                return data
        except Exception:
            pass

    conn = await asyncpg.connect(DB_URL)

    try:
        if mode == SearchMode.SEMANTIC:
            results = await semantic_search(conn, query, domain, limit)
        elif mode == SearchMode.KEYWORD:
            results = await keyword_search(conn, query, domain, limit)
        elif mode == SearchMode.METRIC:
            results = await metric_search(conn, query, domain, limit)
        elif mode == SearchMode.TEMPORAL:
            results = await temporal_search(conn, query, domain, limit)
        elif mode == SearchMode.HYBRID:
            results = await hybrid_search(conn, query, domain, limit)
        else:
            results = await semantic_search(conn, query, domain, limit)

        # [RERANKER v2] non-HYBRID modes (HYBRID already gated inside hybrid_search)
        if mode != SearchMode.HYBRID and _reranker_enabled() and results and len(results) > 1:
            logger.info(
                "🔍 [RERANKER] Re-ranking %s results (%s)...",
                len(results),
                mode.value,
            )
            results = await rerank_results(query, results)

        if results:
            node_ids = [r["id"] for r in results]
            await conn.execute(
                "UPDATE knowledge_nodes SET usage_count = usage_count + 1 WHERE id = ANY($1)",
                node_ids,
            )

        result_text = (
            "\n".join(
                [
                    f"[{mode.value}] Sim {r.get('similarity', 0):.2f} (Rerank {r.get('rerank_score', 0):.2f}): {r['content'][:200]}..."
                    for r in results
                ]
            )
            if results
            else "No relevant knowledge found."
        )

        response = {
            "mode": mode.value,
            "query": query,
            "domain": domain,
            "results_count": len(results),
            "result_text": result_text,
            "results": results,
            "node_ids": [str(r["id"]) for r in results],
        }

        if use_cache:
            try:
                await rd.set(cache_key, json.dumps(response), ex=3600)
            except Exception:
                pass

        return response

    finally:
        await conn.close()
