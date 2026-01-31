import asyncio
import os
import asyncpg
import json

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

async def get_stats():
    try:
        conn = await asyncpg.connect(DB_URL)
        
        # 1. Cache entries
        cache_count = await conn.fetchval("SELECT count(*) FROM semantic_ai_cache")
        
        # 2. Cache hits (total usage_count)
        cache_hits = await conn.fetchval("SELECT sum(usage_count) FROM semantic_ai_cache") or 0
        
        # 3. Local routes (approximated from interaction logs if we had a flag, but for now we can look at logs)
        # Note: We haven't explicitly flagged "local" in interaction_logs yet in a dedicated column, 
        # but we can check metadata.
        local_hits = await conn.fetchval("SELECT count(*) FROM interaction_logs WHERE metadata->>'source' = 'local'") or 0
        
        # 4. Total interactions
        total_interactions = await conn.fetchval("SELECT count(*) FROM interaction_logs")
        
        # 5. Token usage from logs
        total_tokens = await conn.fetchval("SELECT sum(token_usage) FROM interaction_logs") or 0
        
        await conn.close()
        
        return {
            "cache_entries": cache_count,
            "cache_hits": cache_hits,
            "local_hits": local_hits,
            "total_interactions": total_interactions,
            "total_tokens_recorded": total_tokens
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    stats = asyncio.run(get_stats())
    print(json.dumps(stats, indent=2))

