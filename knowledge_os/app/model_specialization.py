"""
Model Specialization - Специализация моделей на типах задач
Оптимизация выбора модели на основе исторической производительности
"""

import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from collections import defaultdict

from app.advanced_ensemble import ModelPerformance, get_advanced_ensemble

logger = logging.getLogger(__name__)


@dataclass
class SpecializationRule:
    """Правило специализации"""
    task_pattern: str
    preferred_models: List[str]
    priority: int  # 1-10
    confidence_threshold: float = 0.7


class ModelSpecializer:
    """Специализатор моделей"""
    
    def __init__(self):
        self.ensemble = get_advanced_ensemble()
        self.specialization_rules: List[SpecializationRule] = []
        self.task_model_mapping: Dict[str, str] = {}  # task_pattern -> best_model
    
    def add_specialization_rule(
        self,
        task_pattern: str,
        preferred_models: List[str],
        priority: int = 5
    ):
        """Добавить правило специализации"""
        rule = SpecializationRule(
            task_pattern=task_pattern,
            preferred_models=preferred_models,
            priority=priority
        )
        self.specialization_rules.append(rule)
        self.specialization_rules.sort(key=lambda r: r.priority, reverse=True)
    
    async def get_specialized_model(
        self,
        goal: str,
        task_type: Optional[str] = None
    ) -> Tuple[str, float]:
        """
        Получить специализированную модель для задачи
        
        Args:
            goal: Цель задачи
            task_type: Тип задачи (если None - определяется автоматически)
        
        Returns:
            (model_name, confidence)
        """
        if task_type is None:
            task_type = self.ensemble._classify_task(goal)
        
        # Проверяем правила специализации
        for rule in self.specialization_rules:
            if rule.task_pattern.lower() in goal.lower():
                # Используем предпочтительные модели из правила
                for model in rule.preferred_models:
                    if model in self.ensemble.models:
                        confidence = rule.confidence_threshold
                        logger.debug(f"🎯 Специализация: {model} для '{rule.task_pattern}' (confidence: {confidence})")
                        return (model, confidence)
        
        # Используем стандартную логику выбора
        model, confidence = await self.ensemble.confidence_based_routing(goal)
        return (model, confidence)
    
    async def learn_specialization(
        self,
        task_type: str,
        model_name: str,
        performance: float
    ):
        """
        Обучение специализации на основе производительности
        
        Args:
            task_type: Тип задачи
            model_name: Модель
            performance: Производительность (0.0-1.0)
        """
        # Обновляем производительность в ensemble
        # (упрощенно - в реальности нужны более детальные метрики)
        self.ensemble.update_model_performance(
            model_name=model_name,
            task_type=task_type,
            success=performance > 0.7,
            confidence=performance,
            latency=1.0  # Упрощенно
        )
        
        # Если производительность высокая - добавляем в специализацию
        if performance > 0.8:
            if task_type not in self.ensemble.model_specialization:
                self.ensemble.model_specialization[task_type] = []
            
            if model_name not in self.ensemble.model_specialization[task_type]:
                self.ensemble.model_specialization[task_type].insert(0, model_name)
                logger.info(f"📚 Обучение: {model_name} добавлена в специализацию для {task_type}")
    
    def get_specialization_report(self) -> Dict[str, Any]:
        """Получить отчет о специализации"""
        return {
            "specialization_rules": len(self.specialization_rules),
            "model_specialization": self.ensemble.model_specialization,
            "performance_stats": self.ensemble.get_model_specialization_stats()
        }

# Глобальный экземпляр
_model_specializer: Optional[ModelSpecializer] = None

def get_model_specializer() -> ModelSpecializer:
    """Получить глобальный экземпляр ModelSpecializer"""
    global _model_specializer
    if _model_specializer is None:
        _model_specializer = ModelSpecializer()
    return _model_specializer
