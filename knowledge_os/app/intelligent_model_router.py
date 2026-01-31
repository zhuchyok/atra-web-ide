"""
Интеллектуальный роутер моделей на основе мировых практик:
- Task Complexity Estimation (оценка сложности задачи)
- Query-Model Interaction Modeling (взаимодействие запрос-модель)
- Multi-Metric Optimization (баланс качества, скорости, стоимости)
- Performance-Cost Trade-off (баланс производительности и стоимости)
"""
import logging
import asyncio
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ModelCapability:
    """Способности модели для разных типов задач"""
    model_name: str
    task_types: List[str]  # Типы задач, с которыми модель справляется
    avg_quality: float  # Среднее качество ответов (0-1)
    avg_latency_ms: float  # Средняя задержка в миллисекундах
    success_rate: float  # Процент успешных ответов (0-1)
    cost_per_token: float  # Стоимость за токен (относительная)
    max_context: int  # Максимальный контекст
    reasoning_capability: float  # Способность к рассуждению (0-1)
    coding_capability: float  # Способность к программированию (0-1)
    speed_capability: float  # Скорость обработки (0-1, выше = быстрее)

@dataclass
class TaskComplexity:
    """Оценка сложности задачи"""
    complexity_score: float  # 0-1, где 1 = очень сложная
    requires_reasoning: bool
    requires_coding: bool
    requires_creativity: bool
    estimated_tokens: int
    task_type: str  # coding, reasoning, fast, general, etc.


class TaskCategory:
    """Категория задачи для совместимости с .value (extended_thinking, fallback)."""
    def __init__(self, value: str):
        self.value = value


class IntelligentModelRouter:
    """
    Интеллектуальный роутер моделей на основе мировых практик:
    1. Task Complexity Estimation
    2. Query-Model Interaction Modeling
    3. Multi-Metric Optimization
    """
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self._pool = None
        self._model_capabilities_cache = {}
        self._cache_ttl = 300  # 5 минут
        
        # Базовые способности моделей (обновляются на основе реальных данных)
        self._base_capabilities = {
            'phi3.5:3.8b': ModelCapability(
                model_name='phi3.5:3.8b',
                task_types=['fast', 'general', 'simple_query'],
                avg_quality=0.7,
                avg_latency_ms=500,
                success_rate=0.85,
                cost_per_token=0.1,
                max_context=128000,
                reasoning_capability=0.6,
                coding_capability=0.65,
                speed_capability=0.9
            ),
            'glm-4.7-flash:q8_0': ModelCapability(  # Ollama модель (Mac Studio)
                model_name='glm-4.7-flash:q8_0',
                task_types=['coding', 'reasoning', 'general'],
                avg_quality=0.85,
                avg_latency_ms=1200,
                success_rate=0.92,
                cost_per_token=0.3,
                max_context=198000,
                reasoning_capability=0.85,
                coding_capability=0.9,
                speed_capability=0.7
            ),
            'qwen2.5-coder:32b': ModelCapability(
                model_name='qwen2.5-coder:32b',
                task_types=['coding', 'complex_coding'],
                avg_quality=0.9,
                avg_latency_ms=2000,
                success_rate=0.95,
                cost_per_token=0.5,
                max_context=128000,
                reasoning_capability=0.75,
                coding_capability=0.95,
                speed_capability=0.5
            ),
            'deepseek-r1-distill-llama:70b': ModelCapability(
                model_name='deepseek-r1-distill-llama:70b',
                task_types=['reasoning', 'complex_reasoning', 'planning'],
                avg_quality=0.95,
                avg_latency_ms=3000,
                success_rate=0.98,
                cost_per_token=0.8,
                max_context=128000,
                reasoning_capability=0.98,
                coding_capability=0.8,
                speed_capability=0.3
            )
        }
    
    async def get_pool(self):
        if not ASYNCPG_AVAILABLE or asyncpg is None:
            return None
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.db_url,
                min_size=1,
                max_size=3,
                max_inactive_connection_lifetime=300
            )
        return self._pool
    
    def estimate_task_complexity(self, prompt: str, category: str = None) -> TaskComplexity:
        """
        Оценка сложности задачи на основе мировых практик
        Использует анализ промпта и категории
        """
        prompt_lower = prompt.lower()
        prompt_length = len(prompt)
        
        # Признаки сложности
        reasoning_indicators = ['подумай', 'логика', 'рассужд', 'анализ', 'стратегия', 'планир', 'архитектура']
        coding_indicators = ['код', 'программируй', 'функция', 'класс', 'алгоритм', 'реализуй', 'напиши код']
        creativity_indicators = ['создай', 'придумай', 'дизайн', 'креатив', 'инновац']
        
        requires_reasoning = any(ind in prompt_lower for ind in reasoning_indicators)
        requires_coding = any(ind in prompt_lower for ind in coding_indicators)
        requires_creativity = any(ind in prompt_lower for ind in creativity_indicators)
        
        # Оценка сложности (0-1)
        complexity_score = 0.0
        
        # Базовая сложность по длине
        if prompt_length < 100:
            complexity_score += 0.1
        elif prompt_length < 500:
            complexity_score += 0.3
        elif prompt_length < 1000:
            complexity_score += 0.5
        else:
            complexity_score += 0.7
        
        # Reasoning добавляет сложности
        if requires_reasoning:
            complexity_score += 0.3
        if requires_coding:
            complexity_score += 0.2
        if requires_creativity:
            complexity_score += 0.2
        
        # Категория влияет на сложность
        if category == 'reasoning':
            complexity_score = max(complexity_score, 0.7)
        elif category == 'coding':
            complexity_score = max(complexity_score, 0.6)
        elif category == 'fast':
            complexity_score = min(complexity_score, 0.4)
        
        complexity_score = min(complexity_score, 1.0)
        
        # Определяем тип задачи
        if requires_coding:
            task_type = 'coding'
        elif requires_reasoning:
            task_type = 'reasoning'
        elif category == 'fast' or prompt_length < 300:
            task_type = 'fast'
        else:
            task_type = 'general'
        
        return TaskComplexity(
            complexity_score=complexity_score,
            requires_reasoning=requires_reasoning,
            requires_coding=requires_coding,
            requires_creativity=requires_creativity,
            estimated_tokens=prompt_length // 4,  # Примерная оценка токенов
            task_type=task_type
        )
    
    async def get_model_capabilities(self, model_name: str) -> Optional[ModelCapability]:
        """Получить актуальные способности модели на основе реальных данных"""
        # Проверяем кэш
        if model_name in self._model_capabilities_cache:
            cached = self._model_capabilities_cache[model_name]
            if (datetime.now() - cached['timestamp']).seconds < self._cache_ttl:
                return cached['capability']
        
        # Получаем из БД (только если asyncpg доступен)
        try:
            pool = await self.get_pool()
            if pool is None:
                raise RuntimeError("asyncpg not available")
            async with pool.acquire() as conn:
                stats = await conn.fetchrow("""
                    SELECT 
                        model_name,
                        AVG(quality_score) as avg_quality,
                        AVG(latency_ms) as avg_latency,
                        COUNT(*) FILTER (WHERE success = true)::float / COUNT(*) as success_rate,
                        COUNT(*) as total_attempts
                    FROM model_performance_log
                    WHERE model_name = $1
                    AND created_at > NOW() - INTERVAL '7 days'
                    GROUP BY model_name
                """, model_name)
                
                if stats and stats['total_attempts'] > 10:
                    # Обновляем базовые способности реальными данными
                    base = self._base_capabilities.get(model_name)
                    if base:
                        updated = ModelCapability(
                            model_name=model_name,
                            task_types=base.task_types,
                            avg_quality=float(stats['avg_quality'] or base.avg_quality),
                            avg_latency_ms=float(stats['avg_latency'] or base.avg_latency_ms),
                            success_rate=float(stats['success_rate'] or base.success_rate),
                            cost_per_token=base.cost_per_token,
                            max_context=base.max_context,
                            reasoning_capability=base.reasoning_capability,
                            coding_capability=base.coding_capability,
                            speed_capability=base.speed_capability
                        )
                        # Кэшируем
                        self._model_capabilities_cache[model_name] = {
                            'capability': updated,
                            'timestamp': datetime.now()
                        }
                        return updated
        except Exception as e:
            logger.debug(f"Error getting model capabilities: {e}")
        
        # Возвращаем базовые способности
        return self._base_capabilities.get(model_name)
    
    def calculate_model_task_fit(
        self,
        model_cap: ModelCapability,
        task_complexity: TaskComplexity
    ) -> float:
        """
        Вычисляет соответствие модели задаче (Query-Model Interaction)
        Возвращает score 0-1, где 1 = идеальное соответствие
        """
        fit_score = 0.0
        
        # 1. Соответствие типу задачи (0-0.4)
        if task_complexity.task_type in model_cap.task_types:
            fit_score += 0.4
        elif task_complexity.task_type == 'coding' and model_cap.coding_capability > 0.7:
            fit_score += 0.3
        elif task_complexity.task_type == 'reasoning' and model_cap.reasoning_capability > 0.7:
            fit_score += 0.3
        
        # 2. Соответствие сложности задачи способностям модели (0-0.3)
        if task_complexity.complexity_score <= 0.4:
            # Простая задача - предпочитаем быстрые модели
            fit_score += model_cap.speed_capability * 0.3
        elif task_complexity.complexity_score <= 0.7:
            # Средняя задача - баланс качества и скорости
            quality_speed_balance = (model_cap.avg_quality * 0.6 + model_cap.speed_capability * 0.4)
            fit_score += quality_speed_balance * 0.3
        else:
            # Сложная задача - предпочитаем качество
            if task_complexity.requires_reasoning:
                fit_score += model_cap.reasoning_capability * 0.3
            elif task_complexity.requires_coding:
                fit_score += model_cap.coding_capability * 0.3
            else:
                fit_score += model_cap.avg_quality * 0.3
        
        # 3. Успешность модели (0-0.2)
        fit_score += model_cap.success_rate * 0.2
        
        # 4. Качество ответов (0-0.1)
        fit_score += model_cap.avg_quality * 0.1
        
        return min(fit_score, 1.0)
    
    def calculate_cost_efficiency_score(
        self,
        model_cap: ModelCapability,
        task_complexity: TaskComplexity
    ) -> float:
        """
        Вычисляет cost-efficiency score (баланс качества и стоимости)
        Используется для cost-aware routing
        """
        # Качество на единицу стоимости
        quality_per_cost = model_cap.avg_quality / max(model_cap.cost_per_token, 0.01)
        
        # Учитываем сложность задачи
        if task_complexity.complexity_score > 0.7:
            # Для сложных задач качество важнее стоимости
            return model_cap.avg_quality * 0.7 + quality_per_cost * 0.3
        else:
            # Для простых задач стоимость важнее
            return quality_per_cost * 0.7 + model_cap.avg_quality * 0.3
    
    def classify_task(self, prompt: str, category: str = None) -> TaskCategory:
        """
        Классифицировать задачу по типу (для fallback и логирования).
        Returns TaskCategory с .value (coding, reasoning, fast, general).
        """
        task_complexity = self.estimate_task_complexity(prompt, category)
        return TaskCategory(task_complexity.task_type)

    def get_fallback_models(
        self,
        model_name: str,
        task_category,
        max_fallbacks: int = 5
    ) -> List[str]:
        """
        Получить список fallback-моделей при недоступности основной.
        task_category — TaskCategory или объект с .value.
        """
        cat_value = getattr(task_category, 'value', str(task_category)) if task_category else 'general'
        all_models = list(self._base_capabilities.keys())
        fallbacks = [m for m in all_models if m != model_name]
        # Приоритет: модели того же типа задачи (по task_types)
        def score(m: str) -> float:
            cap = self._base_capabilities.get(m)
            if not cap:
                return 0.0
            if cat_value in cap.task_types:
                return 1.0
            if 'general' in cap.task_types:
                return 0.5
            return 0.3
        fallbacks.sort(key=score, reverse=True)
        return fallbacks[:max_fallbacks]

    async def select_optimal_model(
        self,
        prompt: str,
        category: str = None,
        available_models: List[str] = None,
        optimize_for: str = 'quality',  # 'quality', 'speed', 'cost', 'balanced'
        prioritize_quality: bool = False,
        prioritize_speed: bool = False,
        **kwargs
    ) -> Tuple[Optional[str], TaskCategory, float]:
        """
        Выбрать оптимальную модель на основе мировых практик.
        
        Args:
            prompt: Промпт задачи
            category: Категория задачи
            available_models: Список доступных моделей
            optimize_for: Что оптимизировать ('quality', 'speed', 'cost', 'balanced')
            prioritize_quality: Приоритет качества (маппится в optimize_for='quality')
            prioritize_speed: Приоритет скорости (маппится в optimize_for='speed')
        
        Returns:
            Tuple[model_name, TaskCategory, confidence_score]
        """
        if prioritize_speed:
            optimize_for = 'speed'
        elif prioritize_quality:
            optimize_for = 'quality'
        if available_models is None:
            available_models = list(self._base_capabilities.keys())
        
        # 1. Оценка сложности задачи
        task_complexity = self.estimate_task_complexity(prompt, category)
        task_category = TaskCategory(task_complexity.task_type)
        
        logger.info(f"📊 [ROUTER] Сложность задачи: {task_complexity.complexity_score:.2f}, тип: {task_complexity.task_type}")
        
        # 2. Получаем способности моделей
        model_scores = {}
        for model_name in available_models:
            model_cap = await self.get_model_capabilities(model_name)
            if not model_cap:
                continue
            
            # 3. Query-Model Interaction: соответствие модели задаче
            fit_score = self.calculate_model_task_fit(model_cap, task_complexity)
            
            # 4. Multi-Metric Optimization
            if optimize_for == 'quality':
                # Оптимизация качества
                final_score = fit_score * 0.6 + model_cap.avg_quality * 0.4
            elif optimize_for == 'speed':
                # Оптимизация скорости
                speed_score = 1.0 - (model_cap.avg_latency_ms / 5000.0)  # Нормализуем до 0-1
                final_score = fit_score * 0.4 + speed_score * 0.6
            elif optimize_for == 'cost':
                # Оптимизация стоимости
                cost_efficiency = self.calculate_cost_efficiency_score(model_cap, task_complexity)
                final_score = fit_score * 0.4 + cost_efficiency * 0.6
            else:  # balanced
                # Сбалансированная оптимизация
                speed_score = 1.0 - (model_cap.avg_latency_ms / 5000.0)
                cost_efficiency = self.calculate_cost_efficiency_score(model_cap, task_complexity)
                final_score = (
                    fit_score * 0.4 +
                    model_cap.avg_quality * 0.3 +
                    speed_score * 0.15 +
                    cost_efficiency * 0.15
                )
            
            model_scores[model_name] = {
                'score': final_score,
                'fit_score': fit_score,
                'capability': model_cap
            }
        
        if not model_scores:
            return None, 0.0
        
        # 5. Выбираем модель с лучшим score
        best_model = max(model_scores.items(), key=lambda x: x[1]['score'])
        model_name, scores = best_model
        
        logger.info(
            f"🎯 [ROUTER] Выбрана модель: {model_name} "
            f"(score: {scores['score']:.3f}, fit: {scores['fit_score']:.3f}, "
            f"quality: {scores['capability'].avg_quality:.2f})"
        )
        
        return model_name, task_category, scores['score']
    
    async def get_alternative_models(
        self,
        prompt: str,
        category: str = None,
        top_n: int = 3
    ) -> List[Tuple[str, float]]:
        """Получить альтернативные модели (для fallback или ensemble)"""
        task_complexity = self.estimate_task_complexity(prompt, category)
        available_models = list(self._base_capabilities.keys())
        
        model_scores = []
        for model_name in available_models:
            model_cap = await self.get_model_capabilities(model_name)
            if not model_cap:
                continue
            
            fit_score = self.calculate_model_task_fit(model_cap, task_complexity)
            model_scores.append((model_name, fit_score))
        
        # Сортируем по score и возвращаем top_n
        model_scores.sort(key=lambda x: x[1], reverse=True)
        return model_scores[:top_n]

# Singleton
_router_instance = None

def get_intelligent_router(db_url: str = None) -> IntelligentModelRouter:
    global _router_instance
    if _router_instance is None:
        import os
        db_url = db_url or os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
        _router_instance = IntelligentModelRouter(db_url)
    return _router_instance
