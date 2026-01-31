"""
Adaptive Learner
Автоматическое обновление примеров на основе feedback для улучшения качества
"""

import asyncio
import logging
import asyncpg
import os
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

class AdaptiveLearner:
    """
    Адаптивное обучение: автоматически обновляет примеры на основе feedback.
    """
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
    
    async def analyze_feedback_and_update_examples(self):
        """
        Анализирует feedback и обновляет примеры в distillation engine.
        """
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Получаем негативный feedback (reroute в облако)
                negative_feedback = await conn.fetch("""
                    SELECT query, response, reroute_reason, quality_score
                    FROM feedback_data
                    WHERE rerouted_to_cloud = TRUE
                    AND created_at > NOW() - INTERVAL '7 days'
                    ORDER BY created_at DESC
                    LIMIT 50
                """)
                
                # Получаем позитивный feedback (успешные локальные ответы)
                positive_feedback = await conn.fetch("""
                    SELECT query, response, routing_source, quality_score
                    FROM feedback_data
                    WHERE rerouted_to_cloud = FALSE
                    AND routing_source IN ('local_mac', 'local_server')
                    AND quality_score >= 0.8
                    AND created_at > NOW() - INTERVAL '7 days'
                    ORDER BY quality_score DESC, created_at DESC
                    LIMIT 20
                """)
                
                # Анализируем паттерны ошибок
                error_patterns = self._extract_error_patterns(negative_feedback)
                
                # Обновляем примеры в distillation engine
                updated_count = await self._update_distillation_examples(
                    conn, negative_feedback, positive_feedback, error_patterns
                )
                
                logger.info(f"✅ [ADAPTIVE LEARNING] Updated {updated_count} examples based on feedback")
                return updated_count
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ [ADAPTIVE LEARNING] Error analyzing feedback: {e}")
            return 0
    
    def _extract_error_patterns(self, negative_feedback: List) -> Dict[str, int]:
        """Извлекает паттерны ошибок из негативного feedback"""
        patterns = {}
        for feedback in negative_feedback:
            reason = feedback.get('reroute_reason', 'unknown')
            patterns[reason] = patterns.get(reason, 0) + 1
        return patterns
    
    async def _update_distillation_examples(
        self,
        conn: asyncpg.Connection,
        negative_feedback: List,
        positive_feedback: List,
        error_patterns: Dict[str, int]
    ) -> int:
        """Обновляет примеры в distillation engine"""
        updated = 0
        
        # Удаляем неэффективные примеры (те, которые часто приводят к reroute)
        for pattern, count in error_patterns.items():
            if count >= 5:  # Если паттерн встречается 5+ раз
                # Находим примеры, связанные с этим паттерном
                await conn.execute("""
                    UPDATE synthetic_training_data
                    SET usage_count = usage_count - 10
                    WHERE category IN (
                        SELECT DISTINCT category
                        FROM feedback_data
                        WHERE reroute_reason = $1
                    )
                """, pattern)
                updated += 1
        
        # Добавляем успешные примеры из позитивного feedback
        for feedback in positive_feedback[:10]:  # Топ-10 успешных
            query = feedback.get('query', '')
            response = feedback.get('response', '')
            
            if query and response:
                # Проверяем, нет ли уже такого примера
                exists = await conn.fetchval("""
                    SELECT COUNT(*) FROM synthetic_training_data
                    WHERE input_query = $1
                """, query[:200])
                
                if not exists:
                    # Добавляем как успешный пример
                    await conn.execute("""
                        INSERT INTO synthetic_training_data
                        (expert_id, category, input_query, bad_response, corrected_response, fix_explanation, usage_count)
                        VALUES ($1, $2, $3, $4, $5, $6, 0)
                    """,
                    'adaptive_learner',
                    'general',
                    query[:500],
                    '',  # Нет плохого ответа
                    response[:1000],
                    'Успешный пример из адаптивного обучения',
                    0)  # Начинаем с 0, будет увеличиваться при использовании
                    updated += 1
        
        return updated
    
    async def prioritize_examples_by_success(self):
        """Приоритизирует примеры на основе успешности"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Обновляем usage_count на основе успешности
                # Примеры с высоким usage_count и низким количеством reroute = приоритетные
                await conn.execute("""
                    UPDATE synthetic_training_data std
                    SET usage_count = usage_count + (
                        SELECT COUNT(*) * 2
                        FROM feedback_data fd
                        WHERE fd.query ILIKE '%' || std.input_query[:50] || '%'
                        AND fd.rerouted_to_cloud = FALSE
                        AND fd.quality_score >= 0.8
                    ) - (
                        SELECT COUNT(*) * 5
                        FROM feedback_data fd
                        WHERE fd.query ILIKE '%' || std.input_query[:50] || '%'
                        AND fd.rerouted_to_cloud = TRUE
                    )
                    WHERE usage_count < 0
                """)
                
                # Удаляем примеры с очень низким usage_count (неэффективные)
                deleted = await conn.execute("""
                    DELETE FROM synthetic_training_data
                    WHERE usage_count < -20
                """)
                
                logger.info(f"✅ [ADAPTIVE LEARNING] Prioritized examples, deleted {deleted} ineffective ones")
                return deleted
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ [ADAPTIVE LEARNING] Error prioritizing examples: {e}")
            return 0

async def run_adaptive_learning_cycle():
    """Запускает цикл адаптивного обучения"""
    learner = AdaptiveLearner()
    
    # Анализируем feedback и обновляем примеры
    updated = await learner.analyze_feedback_and_update_examples()
    
    # Приоритизируем примеры
    deleted = await learner.prioritize_examples_by_success()
    
    logger.info(f"✅ [ADAPTIVE LEARNING] Cycle completed: {updated} updated, {deleted} deleted")
    return updated, deleted

if __name__ == "__main__":
    asyncio.run(run_adaptive_learning_cycle())

