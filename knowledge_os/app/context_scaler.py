"""
Context Scaler для динамического масштабирования контекста.
Анализирует историю запросов и автоматически подбирает оптимальные параметры.
"""

import asyncio
import logging
import asyncpg
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ContextScaler:
    """
    Менеджер для динамического масштабирования контекста.
    Анализирует историю запросов и подбирает оптимальные max_tokens и context_window.
    """
    
    def __init__(self, db_url: str = None):
        import os
        self.db_url = db_url or os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
        self.task_type_stats: Dict[str, Dict] = {}
        
    async def analyze_request_history(self, task_type: str, days: int = 7) -> Dict:
        """Анализировать историю запросов для типа задачи"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Анализируем запросы из semantic_ai_cache
                rows = await conn.fetch("""
                    SELECT 
                        LENGTH(query_text) as prompt_length,
                        LENGTH(response_text) as response_length,
                        performance_score,
                        created_at
                    FROM semantic_ai_cache
                    WHERE created_at > NOW() - INTERVAL '%s days'
                    AND query_text ILIKE '%' || $1 || '%'
                    ORDER BY created_at DESC
                    LIMIT 100
                """, days, task_type)
                
                if not rows:
                    return {"avg_prompt_length": 500, "avg_response_length": 1000, "count": 0}
                
                total_prompt = sum(row['prompt_length'] or 0 for row in rows)
                total_response = sum(row['response_length'] or 0 for row in rows)
                count = len(rows)
                
                return {
                    "avg_prompt_length": total_prompt // count if count > 0 else 500,
                    "avg_response_length": total_response // count if count > 0 else 1000,
                    "max_prompt_length": max((row['prompt_length'] or 0 for row in rows), default=500),
                    "max_response_length": max((row['response_length'] or 0 for row in rows), default=1000),
                    "count": count
                }
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"Error analyzing request history: {e}")
            return {"avg_prompt_length": 500, "avg_response_length": 1000, "count": 0}
    
    def calculate_optimal_params(self, stats: Dict, task_type: str) -> Tuple[int, int]:
        """
        Вычислить оптимальные параметры на основе статистики.
        
        Returns:
            (max_tokens, context_window)
        """
        avg_response = stats.get("avg_response_length", 1000)
        max_response = stats.get("max_response_length", 2000)
        avg_prompt = stats.get("avg_prompt_length", 500)
        
        # Базовые значения
        base_max_tokens = 2000
        base_context = 4000
        
        # Адаптация по типу задачи
        if task_type in ["coding", "refactoring"]:
            # Кодирование требует больше контекста
            max_tokens = int(max_response * 1.5) + 500
            context_window = int((avg_prompt + max_tokens) * 1.2)
        elif task_type in ["analysis", "planning"]:
            # Анализ требует средний контекст
            max_tokens = int(avg_response * 1.3) + 300
            context_window = int((avg_prompt + max_tokens) * 1.1)
        else:
            # Простые задачи
            max_tokens = int(avg_response * 1.2) + 200
            context_window = int((avg_prompt + max_tokens) * 1.05)
        
        # Ограничения
        max_tokens = min(max_tokens, 8000)  # Максимум 8k токенов
        context_window = min(context_window, 16000)  # Максимум 16k контекст
        
        return max_tokens, context_window
    
    async def get_optimal_params(self, task_type: str, prompt_length: int) -> Tuple[int, int]:
        """Получить оптимальные параметры для задачи"""
        # Анализируем историю
        stats = await self.analyze_request_history(task_type)
        
        # Вычисляем параметры
        max_tokens, context_window = self.calculate_optimal_params(stats, task_type)
        
        # Учитываем длину текущего промпта
        if prompt_length > context_window * 0.8:
            context_window = int(prompt_length * 1.3)
        
        logger.debug(f"📏 [CONTEXT SCALER] {task_type}: max_tokens={max_tokens}, context={context_window}")
        
        return max_tokens, context_window

# Глобальный экземпляр
_scaler: Optional[ContextScaler] = None

def get_context_scaler(db_url: str = None) -> ContextScaler:
    """Получить глобальный экземпляр ContextScaler"""
    global _scaler
    if _scaler is None:
        _scaler = ContextScaler(db_url)
    return _scaler

