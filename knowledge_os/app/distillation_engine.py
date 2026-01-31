import logging
import json
import os
import getpass
from typing import List, Dict, Optional
import asyncpg

logger = logging.getLogger(__name__)

USER_NAME = getpass.getuser()
if USER_NAME == 'zhuchyok':
    DEFAULT_DB_URL = f'postgresql://{USER_NAME}@localhost:5432/knowledge_os'
else:
    DEFAULT_DB_URL = 'postgresql://admin:secret@localhost:5432/knowledge_os'

DB_URL = os.getenv('DATABASE_URL', DEFAULT_DB_URL)

class KnowledgeDistiller:
    """
    Engine for synthetic distillation: captures errors and injects corrected patterns
    into future prompts for local models.
    """
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def save_correction(
        self,
        expert_id: str,
        category: str,
        input_query: str,
        bad_response: str,
        corrected_response: str,
        fix_explanation: str
    ) -> bool:
        """Saves a corrected error-response pair for future few-shot learning."""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                await conn.execute("""
                    INSERT INTO synthetic_training_data 
                    (expert_id, category, input_query, bad_response, corrected_response, fix_explanation)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, expert_id, category, input_query, bad_response, corrected_response, fix_explanation)
                logger.info(f"💎 [DISTILLATION] Saved new learning pattern for {category}")
                return True
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error saving distillation pattern: {e}")
            return False

    async def get_relevant_examples(self, query: str, category: str, limit: int = 2) -> str:
        """
        Retrieves relevant few-shot examples for the current query to improve local model performance.
        Uses semantic similarity for better example selection (умнее!).
        Updates usage_count for tracking effectiveness.
        Prioritizes examples with higher performance_score from cache.
        """
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Улучшенный выбор: используем семантическую схожесть
                try:
                    from semantic_cache import get_embedding
                    query_embedding = await get_embedding(query)
                    
                    if query_embedding:
                        # Семантический поиск примеров
                        rows = await conn.fetch("""
                            SELECT 
                                std.id, 
                                std.input_query, 
                                std.corrected_response, 
                                std.fix_explanation,
                                COALESCE(
                                    (SELECT AVG(performance_score) 
                                     FROM semantic_ai_cache 
                                     WHERE query_text ILIKE '%' || std.input_query[:50] || '%'
                                     AND performance_score IS NOT NULL),
                                    0.8
                                ) as avg_performance,
                                (1 - (std.input_query_embedding <=> $1::vector)) as similarity
                            FROM synthetic_training_data std
                            WHERE std.category = $2 
                               OR (1 - (std.input_query_embedding <=> $1::vector)) > 0.7
                            ORDER BY similarity DESC, avg_performance DESC, std.usage_count ASC
                            LIMIT $3
                        """, str(query_embedding), category, limit)
                    else:
                        # Fallback к keyword search
                        rows = await self._get_examples_keyword(conn, query, category, limit)
                except Exception as e:
                    logger.warning(f"Semantic search failed, using keyword: {e}")
                    rows = await self._get_examples_keyword(conn, query, category, limit)
                
                if not rows:
                    return ""

                # Update usage_count for retrieved examples
                example_ids = [row['id'] for row in rows]
                await conn.execute("""
                    UPDATE synthetic_training_data
                    SET usage_count = usage_count + 1
                    WHERE id = ANY($1)
                """, example_ids)

                # Build few-shot context
                context = "\n### LEARNING PATTERNS (PAST CORRECTIONS):\n"
                for row in rows:
                    context += f"Query: {row['input_query']}\n"
                    context += f"Correction: {row['corrected_response']}\n"
                    context += f"Expert Advice: {row['fix_explanation']}\n---\n"
                    
                return context
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error retrieving distillation patterns: {e}")
            return ""
    
    async def _get_examples_keyword(self, conn, query: str, category: str, limit: int):
        """Fallback метод для получения примеров по ключевым словам"""
        # Check if we can use performance_score from cache
        use_performance_ranking = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'semantic_ai_cache' 
                AND column_name = 'performance_score'
            )
        """)
        
        if use_performance_ranking:
            rows = await conn.fetch("""
                SELECT DISTINCT ON (std.id)
                    std.id, 
                    std.input_query, 
                    std.corrected_response, 
                    std.fix_explanation,
                    COALESCE(AVG(cache.performance_score), 0.8) as avg_performance
                FROM synthetic_training_data std
                LEFT JOIN semantic_ai_cache cache 
                    ON cache.query_text ILIKE '%' || std.input_query[:50] || '%'
                WHERE std.category = $1 OR std.input_query ILIKE $2
                GROUP BY std.id, std.input_query, std.corrected_response, std.fix_explanation
                ORDER BY avg_performance DESC, std.usage_count ASC, std.created_at DESC
                LIMIT $3
            """, category, f"%{query[:20]}%", limit)
        else:
            rows = await conn.fetch("""
                SELECT id, input_query, corrected_response, fix_explanation
                FROM synthetic_training_data
                WHERE category = $1 OR input_query ILIKE $2
                ORDER BY usage_count ASC, created_at DESC
                LIMIT $3
            """, category, f"%{query[:20]}%", limit)
        
        return rows

    async def generate_local_upgrade_report(self) -> str:
        """Generates a summary of how many patterns were learned."""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                count = await conn.fetchval("SELECT count(*) FROM synthetic_training_data")
                return f"🧠 Система дистилляции: накоплено {count} паттернов обучения."
            finally:
                await conn.close()
        except Exception as e:
            return f"⚠️ Ошибка дистилляции: {e}"
