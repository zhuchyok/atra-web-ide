"""
Enhanced MCP Server with Multimodal Search
Улучшенный MCP сервер с мультимодальным поиском
"""

import asyncio
import os
import json
import asyncpg
import httpx
import redis.asyncio as redis
from mcp.server.fastmcp import FastMCP
from enhanced_search import (
    enhanced_search_knowledge,
    SearchMode,
    detect_search_mode
)
from global_scout import GlobalScout
from knowledge_graph import KnowledgeGraph, LinkType
from contextual_learner import ContextualMemory, AdaptiveLearner, PersonalizationEngine, NeedPredictor
from translator import KnowledgeTranslator, UILocalizer, MultilingualSearch

# Create FastMCP server
mcp = FastMCP(
    "KnowledgeOS",
    host="0.0.0.0",
    port=8000,
    sse_path="/sse",
    message_path="/messages"
)

# Add /metrics endpoint for Prometheus
@mcp.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint"""
    try:
        from metrics_exporter import get_metrics_exporter
        exporter = get_metrics_exporter()
        metrics_text = await exporter.export_prometheus_metrics()
        from fastapi.responses import Response
        return Response(content=metrics_text, media_type="text/plain")
    except Exception as e:
        from fastapi.responses import Response
        return Response(content=f"# ERROR: {e}\n", media_type="text/plain", status_code=500)

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
        pool = await asyncpg.create_pool(
            os.getenv("DATABASE_URL"),
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
async def search_knowledge(
    query: str,
    domain: str = None,
    mode: str = None,
    limit: int = 5
) -> str:
    """
    Enhanced multimodal search in the Knowledge OS.
    
    Modes:
    - semantic: Semantic search using embeddings (default)
    - keyword: Full-text keyword search
    - metric: Search by numeric metrics (confidence_score, usage_count)
    - temporal: Search by time (today, week, month, recent)
    - hybrid: Combination of semantic + keyword search
    - auto: Automatically detect the best mode (default)
    """
    # Определяем режим
    if mode is None or mode == "auto":
        search_mode, _ = detect_search_mode(query)
    else:
        try:
            search_mode = SearchMode(mode.lower())
        except ValueError:
            search_mode, _ = detect_search_mode(query)
    
    # Выполняем поиск
    result = await enhanced_search_knowledge(
        query=query,
        domain=domain,
        mode=search_mode,
        limit=limit,
        use_cache=True
    )
    
    return result['result_text']

@mcp.tool()
async def search_knowledge_detailed(
    query: str,
    domain: str = None,
    mode: str = None,
    limit: int = 5
) -> str:
    """
    Enhanced multimodal search with detailed results (JSON).
    Returns full search results including metadata.
    """
    if mode is None or mode == "auto":
        search_mode, _ = detect_search_mode(query)
    else:
        try:
            search_mode = SearchMode(mode.lower())
        except ValueError:
            search_mode, _ = detect_search_mode(query)
    
    result = await enhanced_search_knowledge(
        query=query,
        domain=domain,
        mode=search_mode,
        limit=limit,
        use_cache=True
    )
    
    return json.dumps(result, indent=2, ensure_ascii=False, default=str)

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
        
        # Очищаем кеш поиска
        keys = await rd.keys("search:*")
        if keys:
            await rd.delete(*keys)
        
        return f"✅ Knowledge captured and stored. Cache invalidated."

@mcp.tool()
async def validate_knowledge_external(
    knowledge_id: int = None,
    content: str = None,
    domain: str = None
) -> str:
    """
    Validate knowledge through external APIs (GitHub, Stack Overflow, arXiv).
    
    Either provide knowledge_id to validate existing knowledge,
    or provide content and domain to validate new knowledge.
    """
    db_pool = await get_pool()
    scout = GlobalScout()
    
    async with db_pool.acquire() as conn:
        if knowledge_id:
            # Валидируем существующее знание
            node = await conn.fetchrow("""
                SELECT k.id, k.content, d.name as domain
                FROM knowledge_nodes k
                JOIN domains d ON k.domain_id = d.id
                WHERE k.id = $1
            """, knowledge_id)
            
            if not node:
                return f"❌ Knowledge node {knowledge_id} not found"
            
            validation_result = await scout.validate_knowledge_node(
                node["id"],
                node["content"],
                node["domain"]
            )
            
            # Обновляем в БД
            await scout.update_knowledge_validation(conn, node["id"], validation_result)
            
            return json.dumps(validation_result, indent=2, ensure_ascii=False, default=str)
        
        elif content and domain:
            # Валидируем новое знание
            validation_result = await scout.validate_knowledge_node(
                0,  # Временный ID
                content,
                domain
            )
            
            return json.dumps(validation_result, indent=2, ensure_ascii=False, default=str)
        
        else:
            return "❌ Please provide either knowledge_id or (content and domain)"

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
        if not logs:
            return "No new logs to analyze."
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

@mcp.tool()
async def get_graph_stats() -> str:
    """Get statistics about the knowledge graph."""
    graph = KnowledgeGraph()
    stats = await graph.get_graph_stats()
    return json.dumps(stats, indent=2, ensure_ascii=False, default=str)

@mcp.tool()
async def get_user_preferences(user_identifier: str, preference_type: str = None) -> str:
    """
    Get user preferences for personalization.
    
    preference_type: 'domain_preference', 'expert_preference', 'response_style' (optional)
    """
    personalizer = PersonalizationEngine()
    preferences = await personalizer.get_preferences(user_identifier, preference_type)
    return json.dumps(preferences, indent=2, ensure_ascii=False, default=str)

@mcp.tool()
async def predict_user_needs(user_identifier: str, recent_interactions: int = 10) -> str:
    """
    Predict user needs based on interaction history.
    
    recent_interactions: Number of recent interactions to analyze (default: 10)
    """
    predictor = NeedPredictor()
    predictions = await predictor.predict_needs(user_identifier, recent_interactions)
    return json.dumps(predictions, indent=2, ensure_ascii=False, default=str)

@mcp.tool()
async def get_learned_insights(expert_id: str = None, learning_type: str = None, limit: int = 10) -> str:
    """
    Get learned insights from adaptive learning.
    
    expert_id: Filter by expert (optional)
    learning_type: Filter by type (optional)
    limit: Maximum number of insights (default: 10)
    """
    learner = AdaptiveLearner()
    insights = await learner.get_learned_insights(expert_id, learning_type, limit)
    return json.dumps(insights, indent=2, ensure_ascii=False, default=str)

@mcp.tool()
async def find_similar_patterns(
    query: str,
    pattern_type: str = "query_pattern",
    domain: str = None,
    expert: str = None,
    min_success: float = 0.7
) -> str:
    """
    Find similar successful patterns from contextual memory.
    
    pattern_type: 'query_pattern', 'response_pattern', 'interaction_pattern'
    min_success: Minimum success score (default: 0.7)
    """
    memory = ContextualMemory()
    patterns = await memory.find_similar_patterns(query, pattern_type, domain, expert, min_success)
    return json.dumps(patterns, indent=2, ensure_ascii=False, default=str)

@mcp.tool()
async def translate_knowledge(
    knowledge_id: str,
    target_language: str,
    source_language: str = None
) -> str:
    """
    Translate knowledge to target language.
    
    target_language: Language code (en, ru, es, fr, de, zh, ja, ko, pt, it)
    source_language: Source language code (optional, auto-detected if not provided)
    """
    translator = KnowledgeTranslator()
    translated = await translator.translate_knowledge(knowledge_id, target_language, source_language)
    
    if translated:
        return f"✅ Translated to {target_language}:\n{translated}"
    else:
        return f"❌ Failed to translate knowledge {knowledge_id}"

@mcp.tool()
async def search_multilang(
    query: str,
    language: str = "auto",
    domain: str = None,
    limit: int = 10
) -> str:
    """
    Multilingual search in knowledge base.
    
    language: Language code or 'auto' for automatic detection
    domain: Filter by domain (optional)
    limit: Maximum number of results (default: 10)
    """
    searcher = MultilingualSearch()
    results = await searcher.search(query, language, domain, limit)
    
    return json.dumps(results, indent=2, ensure_ascii=False, default=str)

@mcp.tool()
async def get_ui_translation(
    key: str,
    language: str = "en",
    context: str = None
) -> str:
    """
    Get UI translation for a key.
    
    key: Translation key
    language: Language code (default: en)
    context: Context (dashboard, api, telegram, etc.)
    """
    localizer = UILocalizer()
    translation = await localizer.get_translation(key, language, context)
    return translation

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    print("🚀 Knowledge OS MCP Server (Enhanced) starting with MULTIMODAL SEARCH...")
    mcp.run(transport="sse")

