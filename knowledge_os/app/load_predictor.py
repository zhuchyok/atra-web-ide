"""
Load Predictor для предсказания нагрузки и предварительного warmup моделей.
"""

import asyncio
import logging
import asyncpg
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

class LoadPredictor:
    """Предсказатель нагрузки на основе паттернов использования"""
    
    def __init__(self, db_url: str = None):
        import os
        self.db_url = db_url or os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
        self.hourly_patterns: Dict[int, int] = defaultdict(int)  # hour -> request_count
        self.daily_patterns: Dict[int, int] = defaultdict(int)  # weekday -> request_count
        
    async def analyze_usage_patterns(self, days: int = 14) -> Dict:
        """Анализировать паттерны использования"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                rows = await conn.fetch("""
                    SELECT 
                        EXTRACT(HOUR FROM created_at) as hour,
                        EXTRACT(DOW FROM created_at) as weekday,
                        COUNT(*) as request_count
                    FROM semantic_ai_cache
                    WHERE created_at > NOW() - INTERVAL '%s days'
                    GROUP BY hour, weekday
                    ORDER BY hour, weekday
                """, days)
                
                hourly = defaultdict(int)
                daily = defaultdict(int)
                
                for row in rows:
                    hour = int(row['hour'])
                    weekday = int(row['weekday'])
                    count = row['request_count']
                    hourly[hour] += count
                    daily[weekday] += count
                
                return {
                    "hourly": dict(hourly),
                    "daily": dict(daily),
                    "peak_hour": max(hourly.items(), key=lambda x: x[1])[0] if hourly else 14,
                    "peak_day": max(daily.items(), key=lambda x: x[1])[0] if daily else 1
                }
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"Error analyzing patterns: {e}")
            return {"hourly": {}, "daily": {}, "peak_hour": 14, "peak_day": 1}
    
    async def predict_next_hour_load(self) -> float:
        """Предсказать нагрузку на следующий час (0.0-1.0)"""
        patterns = await self.analyze_usage_patterns()
        current_hour = datetime.now().hour
        next_hour = (current_hour + 1) % 24
        
        hourly = patterns.get("hourly", {})
        if not hourly:
            return 0.5  # Средняя нагрузка по умолчанию
        
        # Нормализуем к 0.0-1.0
        max_count = max(hourly.values()) if hourly.values() else 1
        next_hour_count = hourly.get(next_hour, 0)
        
        return min(1.0, next_hour_count / max_count if max_count > 0 else 0.5)
    
    async def should_warmup_models(self) -> bool:
        """Определить, нужно ли прогреть модели"""
        predicted_load = await self.predict_next_hour_load()
        return predicted_load > 0.7  # Высокая ожидаемая нагрузка

# Глобальный экземпляр
_predictor: Optional[LoadPredictor] = None

def get_load_predictor(db_url: str = None) -> LoadPredictor:
    """Получить глобальный экземпляр LoadPredictor"""
    global _predictor
    if _predictor is None:
        _predictor = LoadPredictor(db_url)
    return _predictor

