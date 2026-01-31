"""
Advanced Model Ensembles
Динамический выбор моделей, weighted voting, confidence-based routing
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import statistics

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')


@dataclass
class ModelPerformance:
    """Производительность модели"""
    model_name: str
    task_type: str
    success_rate: float
    average_confidence: float
    average_latency: float
    total_uses: int = 0
    last_used: Optional[datetime] = None


@dataclass
class EnsembleResult:
    """Результат ансамбля"""
    final_result: Any
    confidence: float
    votes: Dict[str, Any]  # model -> result
    weights: Dict[str, float]  # model -> weight
    method: str  # "weighted_voting", "consensus", "best_of_n"


class AdvancedEnsemble:
    """Продвинутый ансамбль моделей"""
    
    def __init__(self):
        self.models = [
            "command-r-plus:104b",
            "deepseek-r1-distill-llama:70b",
            "llama3.3:70b",
            "qwen2.5-coder:32b",
            "phi3.5:3.8b"
        ]
        
        self.model_performance: Dict[str, Dict[str, ModelPerformance]] = defaultdict(dict)
        self.model_specialization: Dict[str, List[str]] = {
            "reasoning": ["deepseek-r1-distill-llama:70b", "command-r-plus:104b"],
            "planning": ["llama3.3:70b", "command-r-plus:104b"],
            "coding": ["qwen2.5-coder:32b", "llama3.3:70b"],
            "fast": ["phi3.5:3.8b", "qwen2.5:3b"],
            "complex": ["command-r-plus:104b", "llama3.3:70b"]
        }
    
    def _classify_task(self, goal: str) -> str:
        """Классифицировать задачу для выбора специализированных моделей"""
        goal_lower = goal.lower()
        
        if any(word in goal_lower for word in ["реши", "объясни", "почему", "reasoning"]):
            return "reasoning"
        elif any(word in goal_lower for word in ["спланируй", "plan", "организуй"]):
            return "planning"
        elif any(word in goal_lower for word in ["код", "code", "функция", "function"]):
            return "coding"
        elif any(word in goal_lower for word in ["быстро", "fast", "просто", "simple"]):
            return "fast"
        elif any(word in goal_lower for word in ["сложн", "complex", "много"]):
            return "complex"
        else:
            return "general"
    
    async def select_models_for_task(
        self,
        goal: str,
        max_models: int = 3
    ) -> List[str]:
        """
        Выбрать модели для задачи
        
        Args:
            goal: Цель задачи
            max_models: Максимум моделей
        
        Returns:
            Список выбранных моделей
        """
        task_type = self._classify_task(goal)
        
        # Получаем специализированные модели
        specialized = self.model_specialization.get(task_type, self.models[:max_models])
        
        # Фильтруем по производительности
        if task_type in self.model_performance:
            performances = self.model_performance[task_type]
            # Сортируем по success_rate и confidence
            sorted_models = sorted(
                specialized,
                key=lambda m: (
                    performances.get(m, ModelPerformance(m, task_type, 0.5, 0.5, 1.0)).success_rate,
                    performances.get(m, ModelPerformance(m, task_type, 0.5, 0.5, 1.0)).average_confidence
                ),
                reverse=True
            )
            return sorted_models[:max_models]
        
        return specialized[:max_models]
    
    async def weighted_voting(
        self,
        model_results: Dict[str, Any],
        weights: Optional[Dict[str, float]] = None
    ) -> EnsembleResult:
        """
        Взвешенное голосование между моделями
        
        Args:
            model_results: Результаты от моделей {model: result}
            weights: Веса моделей (если None - равные веса)
        
        Returns:
            EnsembleResult
        """
        if not model_results:
            return EnsembleResult(
                final_result=None,
                confidence=0.0,
                votes={},
                weights={},
                method="weighted_voting"
            )
        
        # Определяем веса
        if weights is None:
            weights = {model: 1.0 / len(model_results) for model in model_results.keys()}
        
        # Упрощенное голосование (для текстовых результатов)
        # В реальности нужна более сложная логика
        vote_counts = defaultdict(float)
        
        for model, result in model_results.items():
            weight = weights.get(model, 1.0 / len(model_results))
            # Упрощенно - считаем что результат это строка
            result_key = str(result)[:100]  # Первые 100 символов как ключ
            vote_counts[result_key] += weight
        
        # Выбираем результат с максимальным весом
        best_result_key = max(vote_counts.items(), key=lambda x: x[1])[0]
        confidence = vote_counts[best_result_key]
        
        # Находим оригинальный результат
        final_result = next(
            (r for r in model_results.values() if str(r)[:100] == best_result_key),
            list(model_results.values())[0]
        )
        
        return EnsembleResult(
            final_result=final_result,
            confidence=confidence,
            votes=model_results,
            weights=weights,
            method="weighted_voting"
        )
    
    async def confidence_based_routing(
        self,
        goal: str,
        context: Dict[str, Any] = None
    ) -> Tuple[str, float]:
        """
        Маршрутизация по уверенности
        
        Args:
            goal: Цель задачи
            context: Контекст
        
        Returns:
            (model_name, confidence)
        """
        task_type = self._classify_task(goal)
        
        # Получаем модели для задачи
        models = await self.select_models_for_task(goal, max_models=5)
        
        if not models:
            return (self.models[0], 0.5)
        
        # Выбираем модель с наивысшей confidence для этого типа задач
        best_model = models[0]
        best_confidence = 0.5
        
        if task_type in self.model_performance:
            for model in models:
                perf = self.model_performance[task_type].get(model)
                if perf and perf.average_confidence > best_confidence:
                    best_model = model
                    best_confidence = perf.average_confidence
        
        return (best_model, best_confidence)
    
    async def best_of_n(
        self,
        goal: str,
        n: int = 3,
        context: Dict[str, Any] = None
    ) -> EnsembleResult:
        """
        Best-of-N выборка
        
        Args:
            goal: Цель задачи
            n: Количество попыток
            context: Контекст
        
        Returns:
            Лучший результат
        """
        models = await self.select_models_for_task(goal, max_models=n)
        
        # Здесь должна быть логика получения результатов от моделей
        # Упрощенно возвращаем структуру
        results = {}
        for model in models:
            # В реальности здесь вызов модели
            results[model] = f"Result from {model}"
        
        # Выбираем лучший (упрощенно)
        best_model = models[0]
        best_result = results[best_model]
        
        return EnsembleResult(
            final_result=best_result,
            confidence=0.8,  # Упрощенно
            votes=results,
            weights={m: 1.0 / len(models) for m in models},
            method="best_of_n"
        )
    
    def update_model_performance(
        self,
        model_name: str,
        task_type: str,
        success: bool,
        confidence: float,
        latency: float
    ):
        """Обновить производительность модели"""
        if task_type not in self.model_performance:
            self.model_performance[task_type] = {}
        
        if model_name not in self.model_performance[task_type]:
            self.model_performance[task_type][model_name] = ModelPerformance(
                model_name=model_name,
                task_type=task_type,
                success_rate=1.0 if success else 0.0,
                average_confidence=confidence,
                average_latency=latency,
                total_uses=1
            )
        else:
            perf = self.model_performance[task_type][model_name]
            # Обновляем метрики (скользящее среднее)
            perf.success_rate = (perf.success_rate * perf.total_uses + (1.0 if success else 0.0)) / (perf.total_uses + 1)
            perf.average_confidence = (perf.average_confidence * perf.total_uses + confidence) / (perf.total_uses + 1)
            perf.average_latency = (perf.average_latency * perf.total_uses + latency) / (perf.total_uses + 1)
            perf.total_uses += 1
            perf.last_used = datetime.now(timezone.utc)
    
    def get_model_specialization_stats(self) -> Dict[str, Any]:
        """Получить статистику специализации моделей"""
        stats = {}
        
        for task_type, models in self.model_specialization.items():
            if task_type in self.model_performance:
                type_stats = []
                for model in models:
                    perf = self.model_performance[task_type].get(model)
                    if perf:
                        type_stats.append({
                            "model": model,
                            "success_rate": perf.success_rate,
                            "confidence": perf.average_confidence,
                            "uses": perf.total_uses
                        })
                stats[task_type] = type_stats
        
        return stats

# Глобальный экземпляр
_advanced_ensemble: Optional[AdvancedEnsemble] = None

def get_advanced_ensemble() -> AdvancedEnsemble:
    """Получить глобальный экземпляр AdvancedEnsemble"""
    global _advanced_ensemble
    if _advanced_ensemble is None:
        _advanced_ensemble = AdvancedEnsemble()
    return _advanced_ensemble
