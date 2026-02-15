"""
Отслеживание производительности моделей и автоматическое переключение на более мощную модель
"""
import asyncio
import asyncpg
import logging
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Иерархия моделей от простых к сложным
MODEL_HIERARCHY = {
    'fast': ['phi3.5:3.8b', 'glm-4.7-flash:q8_0'],
    'coding': ['phi3.5:3.8b', 'qwen2.5-coder:32b', 'glm-4.7-flash:q8_0'],
    'reasoning': ['phi3.5:3.8b', 'glm-4.7-flash:q8_0'],
    'default': ['phi3.5:3.8b', 'glm-4.7-flash:q8_0']
}

class ModelPerformanceTracker:
    """Отслеживает производительность моделей и предлагает более мощные при неудаче"""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self._pool = None
    
    async def get_pool(self):
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.db_url,
                min_size=1,
                max_size=3,
                max_inactive_connection_lifetime=300
            )
        return self._pool
    
    async def record_attempt(
        self,
        task_id: str,
        model: str,
        category: str,
        success: bool,
        response_length: int = 0,
        latency_ms: float = 0,
        quality_score: float = 0.0
    ):
        """Записать попытку использования модели"""
        try:
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO model_performance_log (
                        task_id, model_name, category, success,
                        response_length, latency_ms, quality_score, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                """, task_id, model, category or 'default', success,
                    response_length, latency_ms, quality_score)
        except Exception as e:
            logger.debug(f"Error recording model performance: {e}")
    
    async def get_model_stats(self, category: str, hours: int = 24) -> Dict[str, Dict]:
        """Получить статистику моделей за последние N часов"""
        try:
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        model_name,
                        COUNT(*) as total_attempts,
                        COUNT(*) FILTER (WHERE success = true) as successful,
                        AVG(latency_ms) as avg_latency,
                        AVG(quality_score) as avg_quality,
                        AVG(response_length) as avg_response_length
                    FROM model_performance_log
                    WHERE category = $1
                    AND created_at > NOW() - INTERVAL '%s hours'
                    GROUP BY model_name
                """ % hours, category or 'default')
                
                stats = {}
                for row in rows:
                    total = row['total_attempts'] or 0
                    successful = row['successful'] or 0
                    stats[row['model_name']] = {
                        'total_attempts': total,
                        'success_rate': (successful / total) if total > 0 else 0.0,
                        'avg_latency': float(row['avg_latency'] or 0),
                        'avg_quality': float(row['avg_quality'] or 0),
                        'avg_response_length': int(row['avg_response_length'] or 0)
                    }
                return stats
        except Exception as e:
            logger.debug(f"Error getting model stats: {e}")
            return {}
    
    async def get_best_model_for_category(self, category: str) -> Optional[str]:
        """Получить лучшую модель для категории на основе статистики"""
        stats = await self.get_model_stats(category, hours=24)
        if not stats:
            # Если нет статистики, используем первую из иерархии
            hierarchy = MODEL_HIERARCHY.get(category or 'default', MODEL_HIERARCHY['default'])
            return hierarchy[0] if hierarchy else None
        
        # Выбираем модель с лучшим success_rate и качеством
        best_model = None
        best_score = 0.0
        
        for model, model_stats in stats.items():
            # Комбинированный score: success_rate * 0.6 + avg_quality * 0.4
            score = (model_stats['success_rate'] * 0.6) + (model_stats['avg_quality'] * 0.4)
            if score > best_score:
                best_score = score
                best_model = model
        
        return best_model
    
    async def should_upgrade_model(
        self,
        task_id: str,
        current_model: str,
        category: str,
        response: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """Определить, нужно ли переключиться на более мощную модель"""
        try:
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                # Проверяем историю попыток для этой задачи
                attempts = await conn.fetch("""
                    SELECT model_name, success, quality_score, response_length
                    FROM model_performance_log
                    WHERE task_id = $1
                    ORDER BY created_at DESC
                    LIMIT 3
                """, task_id)
                
                if not attempts:
                    return False, None
                
                # Если последние 2 попытки неудачные - переключаемся
                recent_failures = sum(1 for a in attempts[:2] if not a['success'])
                if recent_failures >= 2:
                    # Находим более мощную модель в иерархии
                    hierarchy = MODEL_HIERARCHY.get(category or 'default', MODEL_HIERARCHY['default'])
                    try:
                        current_index = hierarchy.index(current_model)
                        if current_index < len(hierarchy) - 1:
                            next_model = hierarchy[current_index + 1]
                            logger.info(f"🔄 [UPGRADE] Переключаемся с {current_model} на {next_model} для задачи {task_id}")
                            return True, next_model
                    except ValueError:
                        # Модель не в иерархии, пробуем первую из списка
                        if hierarchy:
                            return True, hierarchy[0]
                
                # Проверяем качество ответа
                if response:
                    # Если ответ слишком короткий или низкого качества - переключаемся
                    last_attempt = attempts[0]
                    quality = last_attempt.get('quality_score', 0.0)
                    response_len = len(response) if response else 0
                    
                    if quality < 0.5 or response_len < 100:
                        hierarchy = MODEL_HIERARCHY.get(category or 'default', MODEL_HIERARCHY['default'])
                        try:
                            current_index = hierarchy.index(current_model)
                            if current_index < len(hierarchy) - 1:
                                next_model = hierarchy[current_index + 1]
                                logger.info(f"🔄 [UPGRADE] Низкое качество ответа, переключаемся на {next_model}")
                                return True, next_model
                        except ValueError:
                            pass
                
                return False, None
        except Exception as e:
            logger.debug(f"Error checking model upgrade: {e}")
            return False, None
    
    def calculate_quality_score(self, response: str, expected_length: int = 500) -> float:
        """Вычислить оценку качества ответа"""
        if not response or len(response.strip()) < 10:
            return 0.0
        
        score = 0.0
        
        # Длина ответа (0-0.3)
        length_ratio = min(len(response) / expected_length, 1.0)
        score += length_ratio * 0.3
        
        # Наличие структуры (0-0.3)
        has_structure = any(marker in response for marker in ['\n', '•', '-', '1.', '2.', '3.'])
        if has_structure:
            score += 0.3
        
        # Отсутствие ошибок (0-0.2)
        error_indicators = ['⚠️', '❌', 'Error', 'failed', 'недоступен', 'не могу']
        has_errors = any(indicator in response for indicator in error_indicators)
        if not has_errors:
            score += 0.2
        
        # Информативность (0-0.2) - наличие ключевых слов
        informative_keywords = ['решение', 'рекомендация', 'анализ', 'результат', 'вывод']
        has_info = any(keyword in response.lower() for keyword in informative_keywords)
        if has_info:
            score += 0.2
        
        return min(score, 1.0)

# Singleton
_tracker_instance = None

def get_performance_tracker(db_url: str = None) -> ModelPerformanceTracker:
    global _tracker_instance
    if _tracker_instance is None:
        import os
        db_url = db_url or os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
        _tracker_instance = ModelPerformanceTracker(db_url)
    return _tracker_instance
