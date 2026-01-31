"""
Autonomous Distillation для автоматического детектирования успешных ответов
и генерации synthetic variations для augmentation.
"""

import asyncio
import logging
import asyncpg
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AutonomousDistiller:
    """
    Автономный дистиллятор знаний.
    Автоматически детектирует успешные ответы и создает synthetic variations.
    """
    
    def __init__(self, db_url: str = None):
        import os
        self.db_url = db_url or os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
        
    async def detect_successful_responses(self, min_performance: float = 0.8, days: int = 7) -> List[Dict]:
        """Детектировать успешные ответы из кэша"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                rows = await conn.fetch("""
                    SELECT 
                        query_text,
                        response_text,
                        performance_score,
                        routing_source,
                        usage_count,
                        created_at
                    FROM semantic_ai_cache
                    WHERE performance_score >= $1
                    AND created_at > NOW() - INTERVAL '%s days'
                    AND usage_count > 0
                    ORDER BY performance_score DESC, usage_count DESC
                    LIMIT 50
                """, min_performance, days)
                
                return [dict(row) for row in rows]
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"Error detecting successful responses: {e}")
            return []
    
    async def generate_synthetic_variations(self, query: str, response: str, count: int = 3) -> List[Dict]:
        """
        Генерировать synthetic variations запроса для augmentation.
        
        Note: В будущем можно использовать LLM для генерации вариаций.
        Пока возвращаем простые вариации на основе шаблонов.
        """
        variations = []
        
        # Простые вариации (можно улучшить с помощью LLM)
        templates = [
            query,  # Оригинал
            f"Explain: {query}",
            f"Help me with: {query}",
            f"Can you {query.lower()}?",
        ]
        
        for i, template in enumerate(templates[:count]):
            variations.append({
                "input_query": template,
                "corrected_response": response,  # Используем тот же ответ
                "variation_type": "synthetic",
                "source_query": query
            })
        
        return variations
    
    async def save_distillation_examples(self, examples: List[Dict], category: str = "general"):
        """Сохранить примеры дистилляции в БД"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                for example in examples:
                    await conn.execute("""
                        INSERT INTO synthetic_training_data 
                        (expert_id, category, input_query, bad_response, corrected_response, fix_explanation)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT DO NOTHING
                    """,
                    "autonomous_distiller",
                    category,
                    example.get("input_query", ""),
                    "",  # bad_response (не применимо для synthetic)
                    example.get("corrected_response", ""),
                    f"Synthetic variation from autonomous distillation. Source: {example.get('source_query', '')}"
                    )
                
                logger.info(f"✅ [AUTONOMOUS DISTILLATION] Сохранено {len(examples)} примеров для категории {category}")
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error saving distillation examples: {e}")
    
    async def run_autonomous_distillation(self, category: str = "general"):
        """Запустить автономную дистилляцию для категории"""
        logger.info(f"🔬 [AUTONOMOUS DISTILLATION] Запуск для категории {category}")
        
        # Детектируем успешные ответы
        successful = await self.detect_successful_responses(min_performance=0.85)
        
        if not successful:
            logger.info(f"ℹ️ [AUTONOMOUS DISTILLATION] Не найдено успешных ответов для категории {category}")
            return
        
        # Генерируем synthetic variations
        all_examples = []
        for item in successful[:10]:  # Берем топ-10
            query = item.get("query_text", "")
            response = item.get("response_text", "")
            
            if query and response:
                variations = await self.generate_synthetic_variations(query, response, count=2)
                all_examples.extend(variations)
        
        # Сохраняем примеры
        if all_examples:
            await self.save_distillation_examples(all_examples, category)
            logger.info(f"✅ [AUTONOMOUS DISTILLATION] Создано {len(all_examples)} synthetic examples")

# Глобальный экземпляр
_autonomous_distiller: Optional[AutonomousDistiller] = None

def get_autonomous_distiller(db_url: str = None) -> AutonomousDistiller:
    """Получить глобальный экземпляр AutonomousDistiller"""
    global _autonomous_distiller
    if _autonomous_distiller is None:
        _autonomous_distiller = AutonomousDistiller(db_url)
    return _autonomous_distiller

