"""
Model Optimizer - Оптимизация моделей для лучшей работы
Методы улучшения производительности, качества и скорости
"""

import os
import json
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

@dataclass
class ModelOptimizationConfig:
    """Конфигурация оптимизации для модели"""
    model_name: str
    prompt_cache_enabled: bool = True
    batch_size: int = 1
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repetition_penalty: float = 1.1
    streaming: bool = True
    use_memory_mapping: bool = True
    quantization_level: str = "auto"  # auto, Q4, Q6, Q8


class ModelOptimizer:
    """Оптимизатор моделей для улучшения работы"""
    
    # Оптимальные настройки для каждой модели
    MODEL_CONFIGS = {
        "command-r-plus:104b": ModelOptimizationConfig(
            model_name="qwen2.5-coder:32b",  # 104b удалён, алиас на 32b
            prompt_cache_enabled=True,
            batch_size=1,
            max_tokens=4096,
            temperature=0.6,
            top_p=0.95,
            top_k=50,
            repetition_penalty=1.15,
            streaming=True,
            use_memory_mapping=True,
            quantization_level="Q6"
        ),
        "deepseek-r1-distill-llama:70b": ModelOptimizationConfig(
            model_name="phi3.5:3.8b",  # 70b удалён
            prompt_cache_enabled=True,
            batch_size=1,
            max_tokens=4096,
            temperature=0.5,
            top_p=0.9,
            top_k=40,
            repetition_penalty=1.2,
            streaming=True,
            use_memory_mapping=True,
            quantization_level="Q6"
        ),
        "llama3.3:70b": ModelOptimizationConfig(
            model_name="phi3.5:3.8b",  # 70b удалён
            prompt_cache_enabled=True,
            batch_size=1,
            max_tokens=4096,
            temperature=0.7,
            top_p=0.9,
            top_k=40,
            repetition_penalty=1.1,
            streaming=True,
            use_memory_mapping=True,
            quantization_level="Q6"
        ),
        "qwen2.5-coder:32b": ModelOptimizationConfig(
            model_name="qwen2.5-coder:32b",
            prompt_cache_enabled=True,
            batch_size=2,  # Средние модели - можно батчить
            max_tokens=8192,  # Код может быть длинным
            temperature=0.3,  # Низкая для детерминированного кода
            top_p=0.95,
            top_k=50,
            repetition_penalty=1.1,
            streaming=True,
            use_memory_mapping=True,
            quantization_level="Q8"  # Высокое качество для кода
        ),
        "phi3.5:3.8b": ModelOptimizationConfig(
            model_name="phi3.5:3.8b",
            prompt_cache_enabled=True,
            batch_size=4,  # Маленькие модели - можно батчить
            max_tokens=2048,
            temperature=0.7,
            top_p=0.9,
            top_k=40,
            repetition_penalty=1.1,
            streaming=True,
            use_memory_mapping=False,  # Не нужно для маленьких
            quantization_level="Q4"  # Агрессивное квантование
        ),
        "phi3:mini-4k": ModelOptimizationConfig(
            model_name="phi3:mini-4k",
            prompt_cache_enabled=True,
            batch_size=8,  # Очень маленькие - можно батчить много
            max_tokens=1024,
            temperature=0.8,  # Выше для разнообразия
            top_p=0.9,
            top_k=40,
            repetition_penalty=1.05,
            streaming=True,
            use_memory_mapping=False,
            quantization_level="Q4"
        ),
        "qwen2.5:3b": ModelOptimizationConfig(
            model_name="qwen2.5:3b",
            prompt_cache_enabled=True,
            batch_size=8,
            max_tokens=2048,
            temperature=0.7,
            top_p=0.9,
            top_k=40,
            repetition_penalty=1.1,
            streaming=True,
            use_memory_mapping=False,
            quantization_level="Q4"
        ),
        "tinyllama:1.1b-chat": ModelOptimizationConfig(
            model_name="tinyllama:1.1b-chat",
            prompt_cache_enabled=True,
            batch_size=16,  # Максимальный батч для tiny
            max_tokens=512,  # Короткие ответы
            temperature=0.9,  # Высокая для разнообразия
            top_p=0.95,
            top_k=50,
            repetition_penalty=1.0,  # Минимальный
            streaming=True,
            use_memory_mapping=False,
            quantization_level="Q4"
        )
    }
    
    def get_optimized_config(self, model_name: str) -> ModelOptimizationConfig:
        """Получить оптимизированную конфигурацию для модели"""
        return self.MODEL_CONFIGS.get(
            model_name,
            ModelOptimizationConfig(model_name=model_name)  # Дефолтные настройки
        )
    
    def optimize_prompt(self, prompt: str, model_name: str, task_type: str = "general") -> str:
        """
        Оптимизировать промпт для лучшей работы модели
        
        Args:
            prompt: Исходный промпт
            model_name: Имя модели
            task_type: Тип задачи (coding, reasoning, general)
        
        Returns:
            Оптимизированный промпт
        """
        config = self.get_optimized_config(model_name)
        
        # Оптимизация в зависимости от типа задачи
        if task_type == "coding":
            # Для кода: четкие инструкции, примеры
            optimized = f"""Ты - эксперт по программированию. Отвечай точно и структурированно.

Задача:
{prompt}

Требования:
- Код должен быть рабочим и протестированным
- Используй лучшие практики
- Добавь комментарии где необходимо
- Укажи зависимости если нужны

Ответ:"""
        
        elif task_type == "reasoning":
            # Для reasoning: пошаговое рассуждение
            optimized = f"""Реши задачу пошагово, показывая все рассуждения.

Задача:
{prompt}

Шаги решения:
1. Анализ проблемы
2. Поиск подхода
3. Решение
4. Проверка

Решение:"""
        
        elif task_type == "general":
            # Общий промпт: структурированный ответ
            optimized = f"""Ответь на вопрос структурированно и подробно.

Вопрос:
{prompt}

Ответ:"""
        
        else:
            optimized = prompt
        
        return optimized
    
    def get_generation_params(self, model_name: str) -> Dict:
        """Получить оптимальные параметры генерации для модели"""
        config = self.get_optimized_config(model_name)
        
        return {
            "temperature": config.temperature,
            "top_p": config.top_p,
            "top_k": config.top_k,
            "repetition_penalty": config.repetition_penalty,
            "max_tokens": config.max_tokens,
            "stream": config.streaming
        }
    
    def get_batch_size(self, model_name: str) -> int:
        """Получить оптимальный размер батча для модели"""
        config = self.get_optimized_config(model_name)
        return config.batch_size
    
    def should_use_prompt_cache(self, model_name: str) -> bool:
        """Определить, нужно ли использовать кэширование промптов"""
        config = self.get_optimized_config(model_name)
        return config.prompt_cache_enabled
    
    async def optimize_model_selection(
        self,
        task_type: str,
        complexity: str = "medium",
        available_models: List[str] = None
    ) -> Optional[str]:
        """
        Выбрать оптимальную модель для задачи
        
        Args:
            task_type: Тип задачи (coding, reasoning, fast, general)
            complexity: Сложность (low, medium, high, very_high)
            available_models: Список доступных моделей
        
        Returns:
            Имя оптимальной модели
        """
        if available_models is None:
            available_models = list(self.MODEL_CONFIGS.keys())
        
        # Маппинг задачи на модели
        task_model_map = {
            "coding": {
                "low": ["qwen2.5:3b", "phi3.5:3.8b"],
                "medium": ["qwen2.5-coder:32b"],
                "high": ["qwen2.5-coder:32b"],
                "very_high": ["qwen2.5-coder:32b", "phi3.5:3.8b"]
            },
            "reasoning": {
                "low": ["phi3.5:3.8b", "qwen2.5:3b"],
                "medium": ["qwq:32b", "phi3.5:3.8b"],
                "high": ["qwq:32b", "phi3.5:3.8b"],
                "very_high": ["qwen2.5-coder:32b", "phi3.5:3.8b"]
            },
            "fast": {
                "low": ["tinyllama:1.1b-chat", "phi3:mini-4k"],
                "medium": ["phi3.5:3.8b", "qwen2.5:3b"],
                "high": ["qwen2.5-coder:32b"],
                "very_high": ["qwen2.5-coder:32b"]
            },
            "general": {
                "low": ["tinyllama:1.1b-chat", "phi3:mini-4k"],
                "medium": ["phi3.5:3.8b", "qwen2.5:3b"],
                "high": ["qwen2.5-coder:32b", "phi3.5:3.8b"],
                "very_high": ["qwen2.5-coder:32b", "phi3.5:3.8b"]
            }
        }
        
        candidates = task_model_map.get(task_type, {}).get(complexity, [])
        
        # Выбираем первую доступную модель из кандидатов
        for model in candidates:
            if model in available_models:
                logger.info(f"✅ Выбрана оптимальная модель: {model} для {task_type} ({complexity})")
                return model
        
        # Fallback на первую доступную
        if available_models:
            logger.warning(f"⚠️ Используется fallback модель: {available_models[0]}")
            return available_models[0]
        
        return None


async def main():
    """Пример использования"""
    optimizer = ModelOptimizer()
    
    # Получить оптимизированную конфигурацию
    config = optimizer.get_optimized_config("qwen2.5-coder:32b")
    print(f"Конфигурация для qwen2.5-coder:32b:")
    print(f"  Temperature: {config.temperature}")
    print(f"  Batch size: {config.batch_size}")
    print(f"  Max tokens: {config.max_tokens}")
    
    # Оптимизировать промпт
    optimized_prompt = optimizer.optimize_prompt(
        "Напиши функцию для сортировки",
        "qwen2.5-coder:32b",
        "coding"
    )
    print(f"\nОптимизированный промпт:\n{optimized_prompt}")
    
    # Выбрать оптимальную модель
    best_model = await optimizer.optimize_model_selection(
        task_type="coding",
        complexity="high",
        available_models=["qwen2.5-coder:32b", "phi3.5:3.8b"]
    )
    print(f"\nОптимальная модель: {best_model}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
