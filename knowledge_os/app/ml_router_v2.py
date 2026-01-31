"""
ML Router v2
Улучшенный ML-based роутинг с обучением на исторических данных
Singularity 8.0: Intelligent Improvements
"""

import asyncio
import logging
import os
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class MLRouterV2:
    """
    ML-based роутер v2 с обучением на исторических данных.
    Предсказывает оптимальный роут для каждого запроса.
    """
    
    def __init__(self):
        """Инициализация ML Router v2"""
        self.trainer = None
        self._load_trainer()
    
    def _load_trainer(self):
        """Загружает ML тренер"""
        try:
            from ml_router_trainer import get_ml_router_trainer
            self.trainer = get_ml_router_trainer()
            if self.trainer.load_model():
                logger.info("✅ [ML ROUTER V2] Модель загружена успешно")
            else:
                logger.warning("⚠️ [ML ROUTER V2] Модель не найдена, используем эвристики")
        except ImportError as e:
            logger.warning(f"⚠️ [ML ROUTER V2] ML Trainer недоступен: {e}")
            self.trainer = None
    
    def predict_optimal_route(
        self,
        prompt: str,
        task_type: str = "general",
        category: Optional[str] = None,
        expert_name: str = "Виктория",
        features: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, float]:
        """
        Предсказывает оптимальный роут для запроса.
        
        Args:
            prompt: Промпт запроса
            task_type: Тип задачи (coding, general, research)
            category: Категория запроса
            expert_name: Имя эксперта
            features: Дополнительные features
        
        Returns:
            Кортеж (predicted_route, confidence)
        """
        # Если ML модель недоступна, используем эвристики
        if not self.trainer or not self.trainer.model:
            return self._heuristic_routing(prompt, task_type, category)
        
        # Определяем тип задачи, если не указан
        if task_type == "general":
            if any(kw in prompt.lower() for kw in ["код", "программируй", "рефакторинг", "тест"]):
                task_type = "coding"
            elif any(kw in prompt.lower() for kw in ["новости", "тренды", "сейчас", "актуальные"]):
                task_type = "research"
        
        # Подготавливаем features
        prompt_length = len(prompt)
        if features is None:
            features = {}
        
        # Добавляем features из промпта
        features.update({
            "expert_name": expert_name,
            "has_code_keywords": 1 if any(kw in prompt.lower() for kw in ["код", "функция", "класс"]) else 0,
            "has_error_keywords": 1 if any(kw in prompt.lower() for kw in ["ошибка", "баг", "проблема"]) else 0,
        })
        
        # Предсказываем оптимальный роут
        predicted_route = self.trainer.predict_optimal_route(
            task_type=task_type,
            prompt_length=prompt_length,
            category=category,
            features=features
        )
        
        if predicted_route:
            # Вычисляем confidence (упрощенно, можно улучшить)
            confidence = 0.8  # По умолчанию
            if self.trainer.model:
                # Можно использовать predict_proba для более точной confidence
                try:
                    # Для упрощения используем фиксированную confidence
                    # В реальности можно использовать predict_proba
                    confidence = 0.85
                except:
                    pass
            
            logger.info(f"🤖 [ML ROUTER V2] Предсказан роут: {predicted_route} (confidence: {confidence:.2f})")
            return (predicted_route, confidence)
        else:
            # Fallback на эвристики
            return self._heuristic_routing(prompt, task_type, category)
    
    def _heuristic_routing(
        self,
        prompt: str,
        task_type: str,
        category: Optional[str]
    ) -> Tuple[str, float]:
        """
        Эвристический роутинг (fallback, если ML модель недоступна).
        
        Returns:
            Кортеж (route, confidence)
        """
        prompt_lower = prompt.lower()
        
        # Кодинговые задачи -> локальные модели
        if task_type == "coding" or category == "coding":
            return ("local", 0.7)
        
        # Исследовательские задачи -> веб-поиск
        if any(kw in prompt_lower for kw in ["новости", "тренды", "сейчас", "актуальные"]):
            return ("veronica_web", 0.8)
        
        # Короткие запросы -> локальные модели
        if len(prompt) < 100:
            return ("local", 0.6)
        
        # Длинные/сложные запросы -> облако
        if len(prompt) > 500:
            return ("cloud", 0.7)
        
        # По умолчанию -> локальные модели
        return ("local", 0.5)
    
    async def should_use_ml_routing(self) -> bool:
        """
        Проверяет, следует ли использовать ML роутинг.
        
        Returns:
            True если ML роутинг доступен и обучен
        """
        return self.trainer is not None and self.trainer.model is not None

# Singleton instance
_ml_router_v2_instance: Optional[MLRouterV2] = None

def get_ml_router_v2() -> MLRouterV2:
    """Получить singleton экземпляр ML Router v2"""
    global _ml_router_v2_instance
    if _ml_router_v2_instance is None:
        _ml_router_v2_instance = MLRouterV2()
    return _ml_router_v2_instance

