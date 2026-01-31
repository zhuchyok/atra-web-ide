import asyncio
import os
import json
import asyncpg
import httpx
import redis.asyncio as redis
from mcp.server.fastmcp import FastMCP

# Create FastMCP server
mcp = FastMCP(
    "KnowledgeOS",
    host="0.0.0.0",
    port=8000,
    sse_path="/sse",
    message_path="/messages"
)

# Database connection pool and shared resources
pool = None
redis_client = None
VECTOR_CORE_URL = "http://localhost:8001"

async def get_embedding(text: str) -> list:
    """Get embedding from VectorCore microservice."""
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{VECTOR_CORE_URL}/encode", json={"text": text}, timeout=30.0)
        response.raise_for_status()
        return response.json()["embedding"]

async def get_pool():
    global pool
    if pool is None:
        db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
        pool = await asyncpg.create_pool(
            db_url,
            min_size=2,
            max_size=5,  # Уменьшено для предотвращения перегрузки БД
            max_inactive_connection_lifetime=300
        )
    return pool

async def get_redis():
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url("redis://localhost:6379", decode_responses=True)
    return redis_client

@mcp.tool()
async def search_knowledge(query: str, domain: str = None) -> str:
    """Semantic search in the Knowledge OS with REDIS caching."""
    db_pool = await get_pool()
    rd = await get_redis()
    
    # Пытаемся получить из кеша
    cache_key = f"search:{query}:{domain or 'global'}"
    cached_data = await rd.get(cache_key)
    if cached_data:
        try:
            data = json.loads(cached_data)
            print(f"⚡ [CACHE HIT] for query: {query}")
            # Increment usage_count even on cache hit
            async with db_pool.acquire() as conn:
                await conn.execute("UPDATE knowledge_nodes SET usage_count = usage_count + 1 WHERE id = ANY($1)", data['node_ids'])
            return data['result_text']
        except Exception:
            # If cache format is old, ignore and re-search
            pass

    # Получение эмбеддинга через VectorCore
    embedding = await get_embedding(query)
    
    async with db_pool.acquire() as conn:

        sql = """
            SELECT id, content, confidence_score, usage_count,
                   (1 - (embedding <=> $1::vector)) as similarity
            FROM knowledge_nodes 
            WHERE confidence_score > 0.3
        """
        params = [str(embedding)]
        
        if domain:
            sql += " AND domain_id = (SELECT id FROM domains WHERE name = $2)"
            params.append(domain)
            
        sql += " ORDER BY similarity DESC LIMIT 5"
        results = await conn.fetch(sql, *params)
        
        if not results:
            return "No relevant knowledge found."
        
        # Increment usage_count
        node_ids = [r['id'] for r in results]
        await conn.execute("UPDATE knowledge_nodes SET usage_count = usage_count + 1 WHERE id = ANY($1)", node_ids)
        
        result_text = "\n".join([f"Similarity {r['similarity']:.2f}: {r['content']}" for r in results])
        
        # Сохраняем в кеш на 1 час (текст + ID узлов)
        cache_payload = json.dumps({
            "result_text": result_text,
            "node_ids": node_ids
        })
        await rd.set(cache_key, cache_payload, ex=3600)
        return result_text

@mcp.tool()
async def capture_knowledge(content: str, domain: str, metadata: dict = None) -> str:
    """Save new knowledge and INVALIDATE relevant search cache."""
    db_pool = await get_pool()
    rd = await get_redis()
    
    embedding = await get_embedding(content)
    
    async with db_pool.acquire() as conn:

        domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = $1", domain)
        if not domain_id:
            domain_id = await conn.fetchval("INSERT INTO domains (name) VALUES ($1) RETURNING id", domain)
        
        # Автоматическая верификация для узлов с высоким confidence_score
        metadata_dict = metadata or {}
        confidence_score = metadata_dict.get('confidence_score', 0.0)
        is_verified = False
        
        # Автоматически верифицируем узлы с confidence_score >= 0.9
        if confidence_score >= 0.9:
            is_verified = True
            metadata_dict['auto_verified'] = True
            metadata_dict['auto_verified_reason'] = f'High confidence_score: {confidence_score}'
        
        await conn.execute("""
            INSERT INTO knowledge_nodes (domain_id, content, embedding, metadata, confidence_score, is_verified) 
            VALUES ($1, $2, $3, $4, $5, $6)
        """, domain_id, content, str(embedding), json.dumps(metadata_dict), confidence_score, is_verified)
        
        # Очищаем кеш поиска, чтобы новые знания были видны
        keys = await rd.keys("search:*")
        if keys: await rd.delete(*keys)
        
        return f"✅ Knowledge captured and stored. Cache invalidated."

@mcp.tool()
async def get_logs_for_reflexion(limit: int = 10) -> str:
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        logs = await conn.fetch("""
            SELECT id, user_query, assistant_response 
            FROM interaction_logs 
            WHERE metadata->>'analyzed' IS NULL OR metadata->>'analyzed' = 'false'
            LIMIT $1
        """, limit)
        if not logs: return "No new logs to analyze."
        return json.dumps([dict(l) for l in logs])

@mcp.tool()
async def mark_log_analyzed(log_id: int, status: bool = True):
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE interaction_logs 
            SET metadata = jsonb_set(COALESCE(metadata, '{}'), '{analyzed}', $1)
            WHERE id = $2
        """, json.dumps(status), log_id)
        return f"Log {log_id} marked as analyzed."

# Prometheus metrics endpoint
@mcp.custom_route("/metrics", methods=["GET"])
async def metrics_endpoint(request):
    """Prometheus metrics endpoint"""
    from starlette.responses import Response
    from starlette.requests import Request
    try:
        from metrics_exporter import get_metrics_exporter
        exporter = get_metrics_exporter()
        metrics_text = await exporter.export_prometheus_metrics()
        return Response(content=metrics_text, media_type="text/plain")
    except Exception as e:
        import traceback
        error_msg = f"# ERROR: {e}\n# Traceback: {traceback.format_exc()}\n"
        return Response(
            content=error_msg,
            media_type="text/plain",
            status_code=500
        )

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    print("🚀 Knowledge OS MCP Server starting with REDIS CACHE & VectorCore...")
    mcp.run(transport="sse")
