"""
[SINGULARITY 10.0+] Episodic Memory Manager.
Stores specific user preferences, behavioral patterns, and recurring decisions.
Unlike LongTermMemory (which is task-based), EpisodicMemory is relationship-based.
"""

import logging
import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

class EpisodicMemoryManager:
    """
    Manages episodic memory: user preferences, style, and recurring patterns.
    """
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def save_episode(
        self,
        user_key: str,
        project_context: str,
        episode_type: str,  # 'preference', 'pattern', 'decision'
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Save a specific episodic memory."""
        if not user_key or not content:
            return
            
        try:
            import asyncpg
            conn = await asyncpg.connect(self.db_url)
            try:
                # Ensure table exists (idempotent)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS episodic_memory (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_key TEXT NOT NULL,
                        project_context TEXT NOT NULL,
                        episode_type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS idx_episodic_memory_user_project ON episodic_memory(user_key, project_context);
                """)
                
                # Check for duplicates or updates (simple logic: same type and user)
                # For preferences, we might want to update instead of insert
                if episode_type == 'preference':
                    existing = await conn.fetchval("""
                        SELECT id FROM episodic_memory 
                        WHERE user_key = $1 AND episode_type = $2 AND content = $3
                    """, user_key, episode_type, content)
                    if existing:
                        await conn.execute("UPDATE episodic_memory SET updated_at = NOW() WHERE id = $1", existing)
                        return

                await conn.execute("""
                    INSERT INTO episodic_memory (user_key, project_context, episode_type, content, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                """, user_key, project_context or "default", episode_type, content, json.dumps(metadata or {}))
                
                logger.info(f"🧠 [EPISODIC MEMORY] Saved {episode_type} for {user_key}")
            finally:
                await conn.close()
        except Exception as e:
            logger.debug("episodic_memory save_episode: %s", e)

    async def get_episodes(
        self,
        user_key: str,
        project_context: str,
        limit: int = 10
    ) -> str:
        """Retrieve relevant episodes for context enrichment."""
        if not user_key:
            return ""
            
        try:
            import asyncpg
            conn = await asyncpg.connect(self.db_url)
            try:
                # Check if table exists
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'episodic_memory'
                    )
                """)
                if not table_exists:
                    return ""

                rows = await conn.fetch("""
                    SELECT episode_type, content, metadata
                    FROM episodic_memory
                    WHERE user_key = $1 AND (project_context = $2 OR project_context = 'default')
                    ORDER BY updated_at DESC
                    LIMIT $3
                """, user_key, project_context or "default", limit)
                
                if not rows:
                    return ""
                
                parts = ["--- ПЕРСОНАЛЬНЫЕ ПРЕДПОЧТЕНИЯ И ОПЫТ ---"]
                for r in rows:
                    etype = r['episode_type'].upper()
                    content = r['content']
                    parts.append(f"[{etype}] {content}")
                
                return "\n".join(parts)
            finally:
                await conn.close()
        except Exception as e:
            logger.debug("episodic_memory get_episodes: %s", e)
        return ""

_instance = None
def get_episodic_memory_manager():
    global _instance
    if _instance is None:
        _instance = EpisodicMemoryManager()
    return _instance
