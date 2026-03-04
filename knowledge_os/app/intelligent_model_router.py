"""
Интеллектуальный роутер моделей на основе мировых практик:
- Task Complexity Estimation (оценка сложности задачи)
- Query-Model Interaction Modeling (взаимодействие запрос-модель)
- Multi-Metric Optimization (баланс качества, скорости, стоимости)
- Performance-Cost Trade-off (баланс производительности и стоимости)
"""

import asyncio
import logging

try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

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
            # УРОВЕНЬ 1: Гроссмейстеры (30B+) - Основной интеллект
            "victoria-wisdom-v3.5": ModelCapability(
                model_name="victoria-wisdom-v3.5",
                task_types=[
                    "reasoning",
                    "complex_reasoning",
                    "planning",
                    "architecture",
                    "strategy",
                    "coding",
                    "execution",
                    "general",
                    "vip",
                ],
                avg_quality=0.99,
                avg_latency_ms=3000,
                success_rate=0.99,
                cost_per_token=1.0,
                max_context=128000,
                reasoning_capability=0.99,
                coding_capability=0.99,
                speed_capability=0.4,
            ),
            # УРОВЕНЬ 2: Старшие офицеры (14B) - Аналитика и данные
            "deepseek-r1:14b": ModelCapability(
                model_name="deepseek-r1:14b",
                task_types=["reasoning", "analysis", "data_processing", "general"],
                avg_quality=0.92,
                avg_latency_ms=1500,
                success_rate=0.95,
                cost_per_token=0.4,
                max_context=128000,
                reasoning_capability=0.92,
                coding_capability=0.8,
                speed_capability=0.6,
            ),
            # УРОВЕНЬ 3: Специалисты (5B-7B) - Зрение и узкие задачи
            "minicpm-v:latest": ModelCapability(
                model_name="minicpm-v:latest",
                task_types=["vision", "image_analysis", "ocr"],
                avg_quality=0.88,
                avg_latency_ms=1000,
                success_rate=0.94,
                cost_per_token=0.3,
                max_context=8192,
                reasoning_capability=0.7,
                coding_capability=0.5,
                speed_capability=0.7,
            ),
            # УРОВЕНЬ 4: Пехота (< 2B) - Быстрые задачи и поиск
            "tinyllama:1.1b-chat": ModelCapability(
                model_name="tinyllama:1.1b-chat",
                task_types=["fast", "simple_query", "classification"],
                avg_quality=0.5,
                avg_latency_ms=300,
                success_rate=0.8,
                cost_per_token=0.05,
                max_context=2048,
                reasoning_capability=0.3,
                coding_capability=0.2,
                speed_capability=0.95,
            ),
            "lfm2.5-thinking:1.2b": ModelCapability(
                model_name="lfm2.5-thinking:1.2b",
                task_types=["fast", "logic_check", "summarization"],
                avg_quality=0.6,
                avg_latency_ms=400,
                success_rate=0.85,
                cost_per_token=0.06,
                max_context=32768,
                reasoning_capability=0.6,
                coding_capability=0.3,
                speed_capability=0.9,
            ),
            "moondream:latest": ModelCapability(
                model_name="moondream:latest",
                task_types=["vision", "fast_vision"],
                avg_quality=0.7,
                avg_latency_ms=500,
                success_rate=0.9,
                cost_per_token=0.1,
                max_context=4096,
                reasoning_capability=0.4,
                coding_capability=0.1,
                speed_capability=0.85,
            ),
            # РЕЗЕРВ СТАВКИ: Тяжеловесы (Только как Fallback)
            "qwq:32b": ModelCapability(
                model_name="qwq:32b",
                task_types=["fallback", "extreme_reasoning"],
                avg_quality=0.95,
                avg_latency_ms=4000,
                success_rate=0.97,
                cost_per_token=5.0,  # Заградительная цена
                max_context=128000,
                reasoning_capability=0.99,
                coding_capability=0.8,
                speed_capability=0.1,
            ),
            "deepseek-r1:32b": ModelCapability(
                model_name="deepseek-r1:32b",
                task_types=["fallback", "extreme_logic"],
                avg_quality=0.96,
                avg_latency_ms=5000,
                success_rate=0.98,
                cost_per_token=5.0,  # Заградительная цена
                max_context=128000,
                reasoning_capability=0.99,
                coding_capability=0.85,
                speed_capability=0.1,
            ),
            "glm-4.7-flash:latest": ModelCapability(
                model_name="glm-4.7-flash:latest",
                task_types=["fallback", "long_context"],
                avg_quality=0.85,
                avg_latency_ms=1200,
                success_rate=0.92,
                cost_per_token=5.0,  # Заградительная цена
                max_context=198000,
                reasoning_capability=0.85,
                coding_capability=0.9,
                speed_capability=0.7,
            ),
        }

    async def get_pool(self):
        """Получить пул соединений с БД (мировая практика: переиспользование соединений)"""
        if self._pool is None and ASYNCPG_AVAILABLE:
            try:
                self._pool = await asyncpg.create_pool(self.db_url)
            except Exception as e:
                logger.warning(f"Не удалось создать пул БД для роутера: {e}")
        return self._pool

    def estimate_task_complexity(self, prompt: str, category: str = None) -> TaskComplexity:
        """
        Оценивает сложность задачи на основе промпта и категории.
        """
        prompt_lower = (prompt or "").lower()

        # 1. Определяем тип задачи
        task_type = category or "general"
        if not category:
            if any(
                kw in prompt_lower
                for kw in ["код", "функци", "python", "скрипт", "refactor", "рефактор"]
            ):
                task_type = "coding"
            elif any(
                kw in prompt_lower for kw in ["анализ", "исследуй", "подумай", "логика", "reason"]
            ):
                task_type = "reasoning"
            elif len(prompt_lower) < 100:
                task_type = "fast"

        # 2. Оценка сложности (0-1)
        complexity = 0.3  # Базовая сложность

        # Учитываем длину промпта
        if len(prompt_lower) > 2000:
            complexity += 0.4
        elif len(prompt_lower) > 500:
            complexity += 0.2

        # Учитываем ключевые слова сложности
        if any(kw in prompt_lower for kw in ["сложн", "архитектур", "оптимизироват", "переписат"]):
            complexity += 0.2

        # 3. Флаги требований
        requires_reasoning = task_type == "reasoning" or complexity > 0.6
        requires_coding = task_type == "coding"
        requires_creativity = "креатив" in prompt_lower or "стиль" in prompt_lower

        return TaskComplexity(
            complexity_score=min(complexity, 1.0),
            requires_reasoning=requires_reasoning,
            requires_coding=requires_coding,
            requires_creativity=requires_creativity,
            estimated_tokens=len(prompt_lower) // 4,
            task_type=task_type,
        )

    def _generate_dynamic_capability(self, model_name: str) -> ModelCapability:
        """Динамическая генерация способностей для неизвестной модели на основе её имени"""
        name_lower = model_name.lower()

        # Определяем тип по ключевым словам
        task_types = ["general"]
        reasoning = 0.5
        coding = 0.5
        quality = 0.7

        if "coder" in name_lower or "code" in name_lower:
            task_types.extend(["coding", "complex_coding"])
            coding = 0.9
            quality = 0.85
        if "reason" in name_lower or "qwq" in name_lower or "thought" in name_lower:
            task_types.extend(["reasoning", "complex_reasoning", "logic"])
            reasoning = 0.9
            quality = 0.9
        if "vision" in name_lower or "llava" in name_lower or "moondream" in name_lower:
            task_types.append("vision")

        # Оценка качества по размеру (если есть в названии)
        if "70b" in name_lower or "104b" in name_lower or "next" in name_lower:
            quality = max(quality, 0.95)
        elif "32b" in name_lower or "30b" in name_lower:
            quality = max(quality, 0.85)

        return ModelCapability(
            model_name=model_name,
            task_types=task_types,
            avg_quality=quality,
            avg_latency_ms=2000,
            success_rate=0.9,
            cost_per_token=0.5,
            max_context=32768,
            reasoning_capability=reasoning,
            coding_capability=coding,
            speed_capability=0.5,
        )

    async def get_model_capabilities(self, model_name: str) -> Optional[ModelCapability]:
        """Получить актуальные способности модели на основе реальных данных или динамически сгенерировать"""
        # 1. Проверяем кэш
        if model_name in self._model_capabilities_cache:
            cached = self._model_capabilities_cache[model_name]
            if (datetime.now() - cached["timestamp"]).seconds < self._cache_ttl:
                return cached["capability"]

        # 2. Пытаемся получить из БД
        try:
            pool = await self.get_pool()
            if pool:
                async with pool.acquire() as conn:
                    stats = await conn.fetchrow(
                        """
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
                    """,
                        model_name,
                    )

                    if stats and stats["total_attempts"] > 10:
                        base = self._base_capabilities.get(
                            model_name
                        ) or self._generate_dynamic_capability(model_name)
                        updated = ModelCapability(
                            model_name=model_name,
                            task_types=base.task_types,
                            avg_quality=float(stats["avg_quality"] or base.avg_quality),
                            avg_latency_ms=float(stats["avg_latency"] or base.avg_latency_ms),
                            success_rate=float(stats["success_rate"] or base.success_rate),
                            cost_per_token=base.cost_per_token,
                            max_context=base.max_context,
                            reasoning_capability=base.reasoning_capability,
                            coding_capability=base.coding_capability,
                            speed_capability=base.speed_capability,
                        )
                        self._model_capabilities_cache[model_name] = {
                            "capability": updated,
                            "timestamp": datetime.now(),
                        }
                        return updated
        except Exception:
            pass

        # 3. Если нет в БД, берем из базовых или генерируем
        cap = self._base_capabilities.get(model_name) or self._generate_dynamic_capability(
            model_name
        )
        self._model_capabilities_cache[model_name] = {
            "capability": cap,
            "timestamp": datetime.now(),
        }
        return cap

    def calculate_model_task_fit(
        self, model_cap: ModelCapability, task_complexity: TaskComplexity
    ) -> float:
        """
        Вычисляет соответствие модели задаче (Query-Model Interaction)
        Возвращает score 0-1, где 1 = идеальное соответствие
        """
        fit_score = 0.0

        # 1. Соответствие типу задачи (0-0.4)
        if task_complexity.task_type in model_cap.task_types:
            fit_score += 0.4
        elif (
            task_complexity.task_type == "coding"
            and model_cap.coding_capability > 0.7
            or task_complexity.task_type == "reasoning"
            and model_cap.reasoning_capability > 0.7
        ):
            fit_score += 0.3

        # 2. Соответствие сложности задачи способностям модели (0-0.3)
        if task_complexity.complexity_score <= 0.4:
            # Простая задача - предпочитаем быстрые модели
            fit_score += model_cap.speed_capability * 0.3
        elif task_complexity.complexity_score <= 0.7:
            # Средняя задача - баланс качества и скорости
            quality_speed_balance = model_cap.avg_quality * 0.6 + model_cap.speed_capability * 0.4
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
        self, model_cap: ModelCapability, task_complexity: TaskComplexity
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
        # [FIX] Если category уже является объектом TaskCategory, извлекаем его значение
        if hasattr(category, "value"):
            category = category.value
        elif isinstance(category, str):
            category = category.lower()

        task_complexity = self.estimate_task_complexity(prompt, category)
        return TaskCategory(task_complexity.task_type)

    def get_fallback_models(
        self, model_name: str, task_category, max_fallbacks: int = 5
    ) -> List[str]:
        """
        Получить список fallback-моделей при недоступности основной.
        task_category — TaskCategory или объект с .value.
        """
        cat_value = (
            getattr(task_category, "value", str(task_category)) if task_category else "general"
        )
        all_models = list(self._base_capabilities.keys())
        fallbacks = [m for m in all_models if m != model_name]

        # Приоритет: модели того же типа задачи (по task_types)
        def score(m: str) -> float:
            cap = self._base_capabilities.get(m)
            if not cap:
                return 0.0
            if cat_value in cap.task_types:
                return 1.0
            if "general" in cap.task_types:
                return 0.5
            return 0.3

        fallbacks.sort(key=score, reverse=True)
        return fallbacks[:max_fallbacks]

    async def select_optimal_model(
        self,
        prompt: str,
        category: str = None,
        available_models: List[str] = None,
        optimize_for: str = "quality",  # 'quality', 'speed', 'cost', 'balanced'
        prioritize_quality: bool = False,
        prioritize_speed: bool = False,
        **kwargs,
    ) -> Tuple[Optional[str], TaskCategory, float]:
        """
        Выбрать оптимальную модель на основе мировых практик.
        [STRICT MODE] Всегда предпочитаем Victoria-Wisdom-v3.5 для снижения нагрузки.
        """
        # [SINGULARITY 24.0] Smart Routing 2.0: Local First + Anti-Hallucination
        # Если это не зрение, всегда пробуем Викторию первой
        if "vision" not in (category or "").lower() and "image" not in prompt.lower():
            # Проверяем, не является ли запрос слишком сложным для локальной модели
            # (например, требует знаний, которых точно нет локально)
            task_complexity = self.estimate_task_complexity(prompt, category)

            # Если сложность экстремальная (>0.9) и мы не в режиме экономии,
            # можно было бы эскалировать, но мы держим курс на локальность.
            return "victoria-wisdom-v3.5", TaskCategory(category or "general"), 1.0

        if prioritize_speed:
            optimize_for = "speed"
        elif prioritize_quality:
            optimize_for = "quality"
        if available_models is None:
            available_models = list(self._base_capabilities.keys())

        # 1. Оценка сложности задачи
        task_complexity = self.estimate_task_complexity(prompt, category)
        task_category = TaskCategory(task_complexity.task_type)

        logger.info(
            f"📊 [ROUTER] Сложность задачи: {task_complexity.complexity_score:.2f}, тип: {task_complexity.task_type}"
        )

        # 2. Получаем способности моделей
        model_scores = {}
        for model_name in available_models:
            model_cap = await self.get_model_capabilities(model_name)
            if not model_cap:
                continue

            # 3. Query-Model Interaction: соответствие модели задаче
            fit_score = self.calculate_model_task_fit(model_cap, task_complexity)

            # 4. Multi-Metric Optimization
            if optimize_for == "quality":
                # Оптимизация качества
                final_score = fit_score * 0.6 + model_cap.avg_quality * 0.4
            elif optimize_for == "speed":
                # Оптимизация скорости
                speed_score = 1.0 - (model_cap.avg_latency_ms / 5000.0)  # Нормализуем до 0-1
                final_score = fit_score * 0.4 + speed_score * 0.6
            elif optimize_for == "cost":
                # Оптимизация стоимости
                cost_efficiency = self.calculate_cost_efficiency_score(model_cap, task_complexity)
                final_score = fit_score * 0.4 + cost_efficiency * 0.6
            else:  # balanced
                # Сбалансированная оптимизация
                speed_score = 1.0 - (model_cap.avg_latency_ms / 5000.0)
                cost_efficiency = self.calculate_cost_efficiency_score(model_cap, task_complexity)
                final_score = (
                    fit_score * 0.4
                    + model_cap.avg_quality * 0.3
                    + speed_score * 0.15
                    + cost_efficiency * 0.15
                )

            model_scores[model_name] = {
                "score": final_score,
                "fit_score": fit_score,
                "capability": model_cap,
            }

        if not model_scores:
            return None, TaskCategory("general"), 0.0

        # 5. Выбираем модель с лучшим score
        best_model = max(model_scores.items(), key=lambda x: x[1]["score"])
        model_name, scores = best_model

        logger.info(
            f"🎯 [ROUTER] Выбрана модель: {model_name} "
            f"(score: {scores['score']:.3f}, fit: {scores['fit_score']:.3f}, "
            f"quality: {scores['capability'].avg_quality:.2f})"
        )

        return model_name, task_category, scores["score"]

    async def get_alternative_models(
        self, prompt: str, category: str = None, top_n: int = 3
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

        db_url = db_url or os.getenv(
            "DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os"
        )
        _router_instance = IntelligentModelRouter(db_url)
    return _router_instance
