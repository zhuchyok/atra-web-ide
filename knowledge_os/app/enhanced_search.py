"""
Enhanced Multimodal Search for Knowledge OS - FIXED
Улучшенный мультимодальный поиск с поддержкой разных типов запросов
"""

import asyncio
import os
import json
import re
import asyncpg
import httpx
import redis.asyncio as redis
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
VECTOR_CORE_URL = "http://localhost:8001"

class SearchMode(Enum):
    """Режимы поиска"""
    SEMANTIC = "semantic"  # Семантический (по умолчанию)
    KEYWORD = "keyword"    # По ключевым словам
    METRIC = "metric"      # По метрикам (числовые значения)
    TEMPORAL = "temporal"  # По временным меткам
    HYBRID = "hybrid"      # Гибридный (семантический + ключевые слова)

class QueryParams:
    """Helper to manage dynamic SQL parameters"""
    def __init__(self, initial_params: List[Any] = None):
        self.params = initial_params or []
    
    def add(self, value: Any) -> str:
        self.params.append(value)
        return f"${len(self.params)}"
    
    def get_all(self) -> List[Any]:
        return self.params

async def get_embedding(text: str) -> List[float]:
    """Получение эмбеддинга через VectorCore"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{VECTOR_CORE_URL}/encode",
            json={"text": text},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()["embedding"]

def detect_search_mode(query: str) -> Tuple[SearchMode, Dict]:
    """Автоматическое определение режима поиска"""
    query_lower = query.lower()
    metadata = {}
    
    # Поиск по метрикам (числовые значения)
    metric_patterns = [
        r'\d+\.?\d*\s*(percent|%|процент)',
        r'\d+\.?\d*\s*(gb|mb|kb|bytes)',
        r'\d+\.?\d*\s*(ms|seconds|минут|часов)',
        r'(больше|меньше|>|<|>=|<=)\s*\d+',
        r'(score|confidence|similarity)\s*[><=]?\s*\d+',
    ]
    if any(re.search(pattern, query_lower) for pattern in metric_patterns):
        return SearchMode.METRIC, metadata
    
    # Поиск по времени
    temporal_patterns = [
        r'(сегодня|вчера|неделю|месяц|год)',
        r'\d{4}-\d{2}-\d{2}',  # Дата YYYY-MM-DD
        r'(last|recent|новые|последние)',
        r'(created|updated|created_at|updated_at)',
    ]
    if any(re.search(pattern, query_lower) for pattern in temporal_patterns):
        return SearchMode.TEMPORAL, metadata
    
    # Ключевые слова (точные совпадения)
    keyword_indicators = [
        'точное совпадение', 'exact match', 'keyword',
        'найди текст', 'find text', 'contains',
    ]
    if any(indicator in query_lower for indicator in keyword_indicators):
        return SearchMode.KEYWORD, metadata
    
    # Гибридный (если есть и семантические, и ключевые слова)
    if len(query.split()) > 5 and any(word.isalnum() and len(word) > 4 for word in query.split()):
        return SearchMode.HYBRID, metadata
    
    # По умолчанию - семантический
    return SearchMode.SEMANTIC, metadata

async def semantic_search(
    conn: asyncpg.Connection,
    query: str,
    domain: Optional[str] = None,
    limit: int = 5
) -> List[Dict]:
    """Семантический поиск через эмбеддинги"""
    embedding = await get_embedding(query)
    qp = QueryParams([str(embedding)])
    
    sql = f"""
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
    conn: asyncpg.Connection,
    query: str,
    domain: Optional[str] = None,
    limit: int = 5
) -> List[Dict]:
    """Поиск по ключевым словам (full-text search)"""
    stop_words = {'и', 'или', 'в', 'на', 'с', 'для', 'the', 'a', 'an', 'and', 'or', 'in', 'on', 'at'}
    keywords = [w.lower() for w in query.split() if w.lower() not in stop_words and len(w) > 2]
    
    if not keywords:
        return []
    
    qp = QueryParams()
    conditions = []
    
    # Создаем условия для каждого ключевого слова
    for keyword in keywords:
        p = qp.add(f"%{keyword}%")
        conditions.append(f"(content ILIKE {p} OR metadata::text ILIKE {p})")
    
    # Placeholder array for similarity ranking
    keyword_placeholders = []
    for keyword in keywords:
        keyword_placeholders.append(qp.add(f"%{keyword}%"))

    sql = f"""
        SELECT id, content, confidence_score, usage_count,
               CASE 
                   WHEN content ILIKE ANY(ARRAY[{', '.join(keyword_placeholders)}]) THEN 1.0
                   ELSE 0.8
               END as similarity,
               created_at, domain_id
        FROM knowledge_nodes 
        WHERE confidence_score > 0.3
        AND ({' OR '.join(conditions)})
    """
    
    if domain:
        sql += f" AND domain_id = (SELECT id FROM domains WHERE name = {qp.add(domain)})"
    
    sql += f" ORDER BY similarity DESC, usage_count DESC LIMIT {qp.add(limit)}"
    
    results = await conn.fetch(sql, *qp.get_all())
    return [dict(r) for r in results]

async def metric_search(
    conn: asyncpg.Connection,
    query: str,
    domain: Optional[str] = None,
    limit: int = 5
) -> List[Dict]:
    """Поиск по метрикам (числовые значения)"""
    numbers = re.findall(r'\d+\.?\d*', query)
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
            if 'больше' in query.lower() or '>' in query:
                conditions.append(f"confidence_score > {qp.add(threshold)}")
            elif 'меньше' in query.lower() or '<' in query:
                conditions.append(f"confidence_score < {qp.add(threshold)}")
            else:
                conditions.append(f"confidence_score >= {qp.add(threshold)}")
        except ValueError:
            pass
    
    if 'usage' in query.lower() or 'использование' in query.lower():
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
    conn: asyncpg.Connection,
    query: str,
    domain: Optional[str] = None,
    limit: int = 5
) -> List[Dict]:
    """Поиск по временным меткам"""
    query_lower = query.lower()
    qp = QueryParams()
    
    if 'сегодня' in query_lower or 'today' in query_lower:
        time_condition = "created_at >= CURRENT_DATE"
    elif 'вчера' in query_lower or 'yesterday' in query_lower:
        time_condition = "created_at >= CURRENT_DATE - INTERVAL '1 day' AND created_at < CURRENT_DATE"
    elif 'неделю' in query_lower or 'week' in query_lower:
        time_condition = "created_at >= NOW() - INTERVAL '7 days'"
    elif 'месяц' in query_lower or 'month' in query_lower:
        time_condition = "created_at >= NOW() - INTERVAL '30 days'"
    elif 'год' in query_lower or 'year' in query_lower:
        time_condition = "created_at >= NOW() - INTERVAL '365 days'"
    elif 'новые' in query_lower or 'recent' in query_lower or 'последние' in query_lower:
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
    conn: asyncpg.Connection,
    query: str,
    domain: Optional[str] = None,
    limit: int = 5
) -> List[Dict]:
    """Гибридный поиск: семантический + ключевые слова"""
    semantic_results = await semantic_search(conn, query, domain, limit * 2)
    keyword_results = await keyword_search(conn, query, domain, limit * 2)
    
    combined = {}
    
    for result in semantic_results:
        node_id = str(result['id'])
        similarity = float(result.get('similarity', 0))
        if node_id not in combined:
            combined[node_id] = result.copy()
            combined[node_id]['similarity'] = similarity * 0.7
        else:
            combined[node_id]['similarity'] += similarity * 0.7
    
    for result in keyword_results:
        node_id = str(result['id'])
        similarity = float(result.get('similarity', 0))
        if node_id not in combined:
            combined[node_id] = result.copy()
            combined[node_id]['similarity'] = similarity * 0.3
        else:
            combined[node_id]['similarity'] += similarity * 0.3
    
    sorted_results = sorted(
        combined.values(),
        key=lambda x: x.get('similarity', 0),
        reverse=True
    )
    
    return sorted_results[:limit]

async def enhanced_search_knowledge(
    query: str,
    domain: Optional[str] = None,
    mode: Optional[SearchMode] = None,
    limit: int = 5,
    use_cache: bool = True
) -> Dict:
    """Улучшенный мультимодальный поиск"""
    if mode is None:
        mode, metadata = detect_search_mode(query)
    else:
        metadata = {}
    
    if use_cache:
        try:
            rd = redis.from_url(REDIS_URL, decode_responses=True)
            cache_key = f"search:{mode.value}:{query}:{domain or 'global'}"
            cached_data = await rd.get(cache_key)
            if cached_data:
                data = json.loads(cached_data)
                print(f"⚡ [CACHE HIT] {mode.value} search: {query}")
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
        
        if results:
            node_ids = [r['id'] for r in results]
            await conn.execute(
                "UPDATE knowledge_nodes SET usage_count = usage_count + 1 WHERE id = ANY($1)",
                node_ids
            )
        
        result_text = "\n".join([
            f"[{mode.value}] Similarity {r.get('similarity', 0):.2f}: {r['content'][:200]}..."
            for r in results
        ]) if results else "No relevant knowledge found."
        
        response = {
            'mode': mode.value,
            'query': query,
            'domain': domain,
            'results_count': len(results),
            'result_text': result_text,
            'results': results,
            'node_ids': [str(r['id']) for r in results],
        }
        
        if use_cache:
            try:
                await rd.set(cache_key, json.dumps(response), ex=3600)
            except Exception:
                pass
        
        return response
        
    finally:
        await conn.close()
