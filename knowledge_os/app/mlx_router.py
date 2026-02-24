"""
MLX Router - Использование Apple MLX для снижения нагрузки на MacBook
Оптимизирован для Apple Silicon с использованием Neural Engine
"""

import logging
import platform
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Проверка доступности MLX
MLX_AVAILABLE = False
MLX_LM_AVAILABLE = False

try:
    import mlx.core as mx
    import mlx.nn as nn
    from mlx_lm import generate, load

    MLX_AVAILABLE = True
    MLX_LM_AVAILABLE = True
    logger.info("✅ MLX доступен для использования")
except ImportError as e:
    logger.warning(f"⚠️ MLX недоступен: {e}")
    MLX_AVAILABLE = False
    MLX_LM_AVAILABLE = False

# Проверка Apple Silicon
IS_APPLE_SILICON = platform.machine() == "arm64"

# Кэш загруженных моделей
_mlx_models_cache: Dict[str, Any] = {}


class MLXRouter:
    """
    Роутер для использования Apple MLX вместо Ollama
    Снижает нагрузку на MacBook через Neural Engine
    """

    def __init__(self):
        self.available = MLX_AVAILABLE and IS_APPLE_SILICON
        self.models_cache = _mlx_models_cache
        self.default_model = (
            "mlx-community/qwen2.5-3b-instruct-4bit"  # Квантованная модель для MacBook (быстрая)
        )

        if self.available:
            logger.info("✅ MLX Router инициализирован (Apple Silicon + Neural Engine)")
        else:
            logger.warning("⚠️ MLX Router недоступен (требуется Apple Silicon)")

    def is_available(self) -> bool:
        """Проверка доступности MLX"""
        return self.available

    def get_model(self, model_name: Optional[str] = None) -> Optional[Any]:
        """
        Получает или загружает модель через MLX

        Args:
            model_name: Имя модели (если None, используется default_model)

        Returns:
            Загруженная модель или None
        """
        if not self.available:
            return None

        model_key = model_name or self.default_model

        # Проверяем кэш
        if model_key in self.models_cache:
            logger.debug(f"✅ [MLX] Используем модель из кэша: {model_key}")
            return self.models_cache[model_key]

        try:
            logger.info(f"🔄 [MLX] Загружаем модель: {model_key}")
            # Загружаем модель через MLX (использует Neural Engine)
            model, tokenizer = load(model_key)

            # Кэшируем модель
            self.models_cache[model_key] = {
                "model": model,
                "tokenizer": tokenizer,
                "loaded_at": datetime.now(),
            }

            logger.info(f"✅ [MLX] Модель загружена: {model_key}")
            return self.models_cache[model_key]

        except Exception as e:
            logger.error(f"❌ [MLX] Ошибка загрузки модели {model_key}: {e}")
            return None

    async def generate_response(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        **kwargs,
    ) -> Optional[str]:
        """
        Генерирует ответ через MLX (использует Neural Engine)

        Args:
            prompt: Текст запроса
            model_name: Имя модели (опционально)
            max_tokens: Максимальное количество токенов
            temperature: Температура генерации
            **kwargs: Дополнительные параметры

        Returns:
            Сгенерированный ответ или None
        """
        if not self.available:
            return None

        try:
            # Получаем модель
            model_data = self.get_model(model_name)
            if not model_data:
                return None

            model = model_data["model"]
            tokenizer = model_data["tokenizer"]

            logger.debug(f"🔄 [MLX] Генерируем ответ (max_tokens={max_tokens})")

            # Генерируем ответ через MLX (использует Neural Engine)
            # MLX автоматически использует Neural Engine для ускорения
            # Используем синхронный вызов, так как MLX не поддерживает async напрямую
            import asyncio

            loop = asyncio.get_event_loop()

            # Правильные параметры для mlx_lm.generate():
            # generate() принимает: prompt, max_tokens, verbose
            # Остальные параметры передаются через **kwargs в stream_generate()
            # НО: temp не поддерживается в текущей версии, используем только max_tokens
            generate_params = {
                "max_tokens": max_tokens,
            }
            # Убираем temp и temperature из kwargs, так как они не поддерживаются
            filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ["temp", "temperature"]}
            generate_params.update(filtered_kwargs)

            response = await loop.run_in_executor(
                None, lambda: generate(model, tokenizer, prompt=prompt, **generate_params)
            )

            if response and len(response) > 10:
                logger.info(
                    f"✅ [MLX] Ответ сгенерирован через Neural Engine ({len(response)} символов)"
                )
                return response
            else:
                logger.warning("⚠️ [MLX] Пустой или слишком короткий ответ")
                return None

        except Exception as e:
            logger.error(f"❌ [MLX] Ошибка генерации ответа: {e}")
            return None

    def get_supported_models(self) -> List[str]:
        """
        Возвращает список поддерживаемых моделей для MLX
        Все 8 моделей из PLAN.md

        Returns:
            Список имен моделей
        """
        if not self.available:
            return []

        # Все 8 моделей из PLAN.md (квантованные для экономии памяти)
        return [
            "mlx-community/command-r-plus-4bit",  # 1. Максимальная мощность, RAG, мультиязычность
            "mlx-community/deepseek-r1-distill-llama-70b-4bit",  # 2. Reasoning, планирование
            "mlx-community/llama-3.3-70b-instruct-4bit",  # 3. Максимальное качество, общие задачи
            "mlx-community/qwen2.5-coder-32b-instruct-4bit",  # 4. Качественный код, рефакторинг
            "mlx-community/phi-3.5-mini-instruct-4bit",  # 5. Быстрые задачи, общие
            "mlx-community/phi-3-mini-4k-instruct-4bit",  # 6. Быстрые ответы, легкие задачи
            "mlx-community/qwen2.5-3b-instruct-4bit",  # 7. Быстрые ответы, общие задачи
            "mlx-community/tinyllama-1.1b-chat-v1.0-4bit",  # 8. Очень быстрые ответы
        ]

    def clear_cache(self):
        """Очищает кэш моделей для освобождения памяти"""
        self.models_cache.clear()
        logger.info("✅ [MLX] Кэш моделей очищен")


# Singleton экземпляр
_mlx_router: Optional[MLXRouter] = None


def get_mlx_router() -> MLXRouter:
    """Получает singleton экземпляр MLX Router"""
    global _mlx_router
    if _mlx_router is None:
        _mlx_router = MLXRouter()
    return _mlx_router


def is_mlx_available() -> bool:
    """Проверяет доступность MLX"""
    return get_mlx_router().is_available()
