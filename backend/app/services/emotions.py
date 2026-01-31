"""
Emotional Modulation Service - Singularity v9.0 Integration
Детекция эмоций и адаптация стиля ответа
"""
import re
from typing import Optional, Dict, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Emotion(Enum):
    """Типы эмоций пользователя"""
    FRUSTRATED = "frustrated"
    RUSHED = "rushed"
    CURIOUS = "curious"
    CALM = "calm"
    CONFUSED = "confused"
    EXCITED = "excited"


# Профили адаптации для каждой эмоции
EMOTION_PROFILES: Dict[Emotion, Dict] = {
    Emotion.FRUSTRATED: {
        "tone": "calm, supportive, patient",
        "detail_level": "high",
        "examples": "more",
        "style_prefix": "I understand this can be frustrating. Let me help you step by step. "
    },
    Emotion.RUSHED: {
        "tone": "concise, direct, efficient",
        "detail_level": "medium",
        "examples": "bullet_points",
        "style_prefix": "Quick answer: "
    },
    Emotion.CURIOUS: {
        "tone": "enthusiastic, detailed, educational",
        "detail_level": "very_high",
        "examples": "with_analogies",
        "style_prefix": "Great question! "
    },
    Emotion.CALM: {
        "tone": "professional, clear, balanced",
        "detail_level": "normal",
        "examples": "standard",
        "style_prefix": ""
    },
    Emotion.CONFUSED: {
        "tone": "clarifying, structured, patient",
        "detail_level": "high",
        "examples": "step_by_step",
        "style_prefix": "Let me clarify that for you. "
    },
    Emotion.EXCITED: {
        "tone": "enthusiastic, encouraging, positive",
        "detail_level": "normal",
        "examples": "engaging",
        "style_prefix": "That's awesome! "
    }
}

# Паттерны для детекции эмоций
EMOTION_PATTERNS: Dict[Emotion, List[str]] = {
    Emotion.FRUSTRATED: [
        r"!{2,}",  # Много восклицательных знаков
        r"не работает",
        r"не понимаю",
        r"опять",
        r"again",
        r"doesn't work",
        r"broken",
        r"wtf",
        r"черт",
        r"почему не",
        r"still not",
        r"frustrated",
    ],
    Emotion.RUSHED: [
        r"срочно",
        r"быстро",
        r"asap",
        r"urgent",
        r"quick",
        r"fast",
        r"сейчас",
        r"немедленно",
        r"дедлайн",
        r"deadline",
    ],
    Emotion.CURIOUS: [
        r"как работает",
        r"почему",
        r"зачем",
        r"what is",
        r"how does",
        r"why",
        r"explain",
        r"объясни",
        r"расскажи",
        r"интересно",
        r"curious",
    ],
    Emotion.CONFUSED: [
        r"\?{2,}",  # Много вопросительных знаков
        r"не понял",
        r"что это",
        r"confused",
        r"don't understand",
        r"what do you mean",
        r"huh",
        r"что значит",
    ],
    Emotion.EXCITED: [
        r"круто",
        r"awesome",
        r"cool",
        r"amazing",
        r"отлично",
        r"супер",
        r"вау",
        r"wow",
        r"great",
        r"love it",
    ]
}


class EmotionDetector:
    """
    Детектор эмоций из текста запроса
    
    Использует паттерны и эвристики для определения
    эмоционального состояния пользователя
    """
    
    def __init__(self):
        self._patterns = {
            emotion: [re.compile(p, re.IGNORECASE) for p in patterns]
            for emotion, patterns in EMOTION_PATTERNS.items()
        }
    
    def detect(self, text: str) -> tuple[Emotion, float]:
        """
        Определить эмоцию из текста
        
        Args:
            text: Текст запроса пользователя
            
        Returns:
            Tuple[Emotion, confidence]: Эмоция и уверенность (0-1)
        """
        scores = {emotion: 0 for emotion in Emotion}
        
        # Подсчёт совпадений паттернов
        for emotion, patterns in self._patterns.items():
            for pattern in patterns:
                matches = pattern.findall(text)
                scores[emotion] += len(matches)
        
        # Анализ пунктуации
        exclamation_count = text.count('!')
        question_count = text.count('?')
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        
        if exclamation_count >= 3:
            scores[Emotion.FRUSTRATED] += 2
        if question_count >= 3:
            scores[Emotion.CONFUSED] += 2
        if caps_ratio > 0.5:
            scores[Emotion.FRUSTRATED] += 1
        
        # Анализ длины сообщения
        if len(text) < 20:
            scores[Emotion.RUSHED] += 1
        elif len(text) > 200:
            scores[Emotion.CURIOUS] += 1
        
        # Определение доминирующей эмоции
        max_score = max(scores.values())
        
        if max_score == 0:
            return Emotion.CALM, 0.5
        
        dominant_emotion = max(scores, key=scores.get)
        confidence = min(max_score / 5, 1.0)  # Нормализация
        
        return dominant_emotion, confidence
    
    def get_profile(self, emotion: Emotion) -> Dict:
        """Получить профиль адаптации для эмоции"""
        return EMOTION_PROFILES.get(emotion, EMOTION_PROFILES[Emotion.CALM])
    
    def adapt_prompt(self, original_prompt: str, emotion: Emotion) -> str:
        """
        Адаптировать системный промпт под эмоцию
        
        Args:
            original_prompt: Оригинальный системный промпт
            emotion: Детектированная эмоция
            
        Returns:
            Адаптированный промпт
        """
        profile = self.get_profile(emotion)
        
        adaptation = f"""
Detected user emotion: {emotion.value}
Adapt your response style:
- Tone: {profile['tone']}
- Detail level: {profile['detail_level']}
- Use examples: {profile['examples']}

{original_prompt}
"""
        return adaptation


# Singleton instance
emotion_detector = EmotionDetector()


def detect_emotion(text: str) -> tuple[Emotion, float]:
    """Утилита для детекции эмоции"""
    return emotion_detector.detect(text)


def get_adapted_prompt(original_prompt: str, user_message: str) -> str:
    """
    Получить адаптированный промпт на основе эмоции пользователя
    
    Args:
        original_prompt: Оригинальный системный промпт
        user_message: Сообщение пользователя
        
    Returns:
        Адаптированный промпт
    """
    emotion, confidence = emotion_detector.detect(user_message)
    
    # Применяем адаптацию только при высокой уверенности
    if confidence >= 0.3 and emotion != Emotion.CALM:
        logger.info(f"Emotion detected: {emotion.value} (confidence: {confidence:.2f})")
        return emotion_detector.adapt_prompt(original_prompt, emotion)
    
    return original_prompt
