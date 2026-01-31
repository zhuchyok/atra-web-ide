"""
Emotion Detector: Детекция эмоций из текста запроса для адаптации стиля ответа

Функционал:
- Детекция эмоций из текста запроса (frustrated, rushed, curious, calm)
- Анализ паттернов (пунктуация, ключевые слова, история взаимодействий)
- Определение эмоционального профиля запроса
- Адаптация стиля ответа на основе эмоции
"""

import asyncio
import os
import json
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Import database connection from evaluator
from evaluator import get_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

# Минимальный порог confidence для детекции эмоции
MIN_EMOTION_CONFIDENCE = 0.5

# Emotion profiles для адаптации стиля ответа
EMOTION_PROFILES = {
    "frustrated": {
        "tone": "calm, supportive",
        "detail_level": "high",
        "examples": "more",
        "speed": "slower"
    },
    "rushed": {
        "tone": "concise, direct",
        "detail_level": "medium",
        "examples": "bullet_points",
        "speed": "fast"
    },
    "curious": {
        "tone": "enthusiastic, detailed",
        "detail_level": "very_high",
        "examples": "with_analogies",
        "speed": "normal"
    },
    "calm": {
        "tone": "professional, clear",
        "detail_level": "normal",
        "examples": "standard",
        "speed": "normal"
    }
}

# Индикаторы эмоций (ключевые слова и паттерны)
EMOTION_INDICATORS = {
    "frustrated": {
        "keywords": ["не работает", "ошибка", "проблема", "помогите", "срочно", "!!!", "???", "невозможно", "не понимаю"],
        "punctuation": ["!!!", "???", "??", "!!"],
        "patterns": [r"\?{2,}", r"!{2,}"]
    },
    "rushed": {
        "keywords": ["быстро", "срочно", "нужно сейчас", "как можно скорее", "срочно", "urgent"],
        "punctuation": [],
        "patterns": []
    },
    "curious": {
        "keywords": ["интересно", "объясни", "почему", "как это работает", "расскажи", "подробнее"],
        "punctuation": ["?"],
        "patterns": [r"\?$"]
    },
    "calm": {
        "keywords": ["пожалуйста", "можно", "хотел бы", "интересует"],
        "punctuation": ["."],
        "patterns": [r"\.$"]
    }
}


@dataclass
class EmotionResult:
    """Результат детекции эмоции"""
    detected_emotion: str  # frustrated, rushed, curious, calm
    confidence: float  # 0.0-1.0
    tone: str  # calm_supportive, concise_direct, etc.
    detail_level: str  # high, medium, very_high, normal
    examples: str  # more, bullet_points, with_analogies, standard
    speed: str  # slower, fast, normal


class EmotionDetector:
    """Класс для детекции эмоций из текста запроса"""
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
    
    def detect_emotion(self, query: str, user_history: Optional[List[str]] = None) -> EmotionResult:
        """
        Детектирует эмоцию из текста запроса.
        
        Args:
            query: Текст запроса пользователя
            user_history: История предыдущих запросов пользователя (опционально)
        
        Returns:
            EmotionResult с детектированной эмоцией и профилем
        """
        query_lower = query.lower()
        
        # Подсчитываем индикаторы для каждой эмоции
        emotion_scores = {}
        
        for emotion, indicators in EMOTION_INDICATORS.items():
            score = 0.0
            total_indicators = 0
            
            # Проверяем ключевые слова
            for keyword in indicators["keywords"]:
                if keyword.lower() in query_lower:
                    score += 1.0
                total_indicators += 1
            
            # Проверяем пунктуацию
            for punct in indicators["punctuation"]:
                if punct in query:
                    score += 0.5
                total_indicators += 0.5
            
            # Проверяем паттерны (regex)
            for pattern in indicators["patterns"]:
                if re.search(pattern, query):
                    score += 0.5
                total_indicators += 0.5
            
            # Нормализуем score (0.0-1.0)
            if total_indicators > 0:
                emotion_scores[emotion] = min(score / total_indicators, 1.0)
            else:
                emotion_scores[emotion] = 0.0
        
        # Анализируем историю (если доступна)
        if user_history:
            recent_emotions = []
            for prev_query in user_history[-3:]:  # Последние 3 запроса
                prev_result = self.detect_emotion(prev_query)
                if prev_result.confidence >= MIN_EMOTION_CONFIDENCE:
                    recent_emotions.append(prev_result.detected_emotion)
            
            # Увеличиваем score для эмоций, которые были недавно
            for emotion in recent_emotions:
                if emotion in emotion_scores:
                    emotion_scores[emotion] = min(emotion_scores[emotion] + 0.2, 1.0)
        
        # Определяем эмоцию с максимальным score
        if not emotion_scores or max(emotion_scores.values()) < MIN_EMOTION_CONFIDENCE:
            # По умолчанию - calm
            detected_emotion = "calm"
            confidence = 0.5
        else:
            detected_emotion = max(emotion_scores, key=emotion_scores.get)
            confidence = emotion_scores[detected_emotion]
        
        # Получаем профиль эмоции
        emotion_profile = EMOTION_PROFILES.get(detected_emotion, EMOTION_PROFILES["calm"])
        
        return EmotionResult(
            detected_emotion=detected_emotion,
            confidence=confidence,
            tone=emotion_profile["tone"],
            detail_level=emotion_profile["detail_level"],
            examples=emotion_profile["examples"],
            speed=emotion_profile["speed"]
        )
    
    async def get_user_history(self, user_identifier: str, limit: int = 5) -> List[str]:
        """Получает историю запросов пользователя"""
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_query
                FROM interaction_logs
                WHERE metadata->>'user_identifier' = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, user_identifier, limit)
            
            return [row['user_query'] for row in rows]
    
    async def detect_emotion_with_history(self, query: str, user_identifier: str) -> EmotionResult:
        """
        Детектирует эмоцию с учетом истории пользователя.
        
        Args:
            query: Текст запроса
            user_identifier: Идентификатор пользователя
        
        Returns:
            EmotionResult с детектированной эмоцией
        """
        # Получаем историю запросов
        user_history = await self.get_user_history(user_identifier)
        
        # Детектируем эмоцию
        return self.detect_emotion(query, user_history)
    
    def create_style_modifier(self, emotion_result: EmotionResult) -> str:
        """
        Создает модификатор промпта на основе эмоции.
        
        Args:
            emotion_result: Результат детекции эмоции
        
        Returns:
            Текст модификатора промпта
        """
        return f"""
ЭМОЦИОНАЛЬНЫЙ КОНТЕКСТ ЗАПРОСА:
- Детектированная эмоция: {emotion_result.detected_emotion} (confidence: {emotion_result.confidence:.2f})
- Тон ответа: {emotion_result.tone}
- Уровень детализации: {emotion_result.detail_level}
- Примеры: {emotion_result.examples}
- Скорость ответа: {emotion_result.speed}

ВАЖНО: Адаптируй стиль ответа в соответствии с эмоцией пользователя.
"""
    
    async def log_emotion(self, interaction_log_id: str, emotion_result: EmotionResult, feedback_score: Optional[int] = None) -> Optional[str]:
        """
        Логирует детектированную эмоцию в БД.
        
        Args:
            interaction_log_id: ID записи в interaction_logs
            emotion_result: Результат детекции эмоции
            feedback_score: Feedback score из interaction_logs (опционально)
        
        Returns:
            ID созданной записи или None
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            try:
                emotion_log_id = await conn.fetchval("""
                    INSERT INTO emotion_logs (
                        interaction_log_id,
                        detected_emotion,
                        emotion_confidence,
                        tone_used,
                        detail_level,
                        feedback_score,
                        created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, NOW())
                    RETURNING id
                """,
                interaction_log_id,
                emotion_result.detected_emotion,
                emotion_result.confidence,
                emotion_result.tone,
                emotion_result.detail_level,
                feedback_score
                )
                
                logger.debug(f"✅ Logged emotion: {emotion_result.detected_emotion} (confidence: {emotion_result.confidence:.2f})")
                return str(emotion_log_id) if emotion_log_id else None
            except Exception as e:
                logger.error(f"❌ Error logging emotion: {e}")
                return None
    
    async def calculate_satisfaction_delta(self, emotion: str, feedback_score: int) -> float:
        """
        Вычисляет изменение удовлетворенности после применения эмоциональной адаптации.
        
        Args:
            emotion: Детектированная эмоция
            feedback_score: Feedback score от пользователя
        
        Returns:
            Delta удовлетворенности (0.0-1.0)
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Получаем средний feedback_score для этой эмоции (с адаптацией)
            avg_feedback_with = await conn.fetchval("""
                SELECT AVG(feedback_score::float)
                FROM emotion_logs
                WHERE detected_emotion = $1
                  AND feedback_score IS NOT NULL
                  AND created_at > NOW() - INTERVAL '7 days'
            """, emotion) or 0.0
            
            # Получаем средний feedback_score без эмоциональной адаптации (baseline)
            # Это можно сделать через A/B тестирование или сравнить с общим средним
            avg_feedback_baseline = await conn.fetchval("""
                SELECT AVG(feedback_score::float)
                FROM interaction_logs
                WHERE feedback_score IS NOT NULL
                  AND created_at > NOW() - INTERVAL '7 days'
            """) or 0.0
            
            # Вычисляем delta
            if avg_feedback_baseline > 0:
                delta = (avg_feedback_with - avg_feedback_baseline) / avg_feedback_baseline
            else:
                delta = 0.0
            
            return delta


if __name__ == "__main__":
    # Тестирование
    detector = EmotionDetector()
    
    test_queries = [
        "Не работает код!!! Помогите срочно!!!",
        "Объясни, как это работает? Интересно узнать подробнее.",
        "Нужно быстро сделать это",
        "Пожалуйста, объясни это"
    ]
    
    for query in test_queries:
        result = detector.detect_emotion(query)
        print(f"Query: {query}")
        print(f"Emotion: {result.detected_emotion} (confidence: {result.confidence:.2f})")
        print(f"Tone: {result.tone}")
        print()

