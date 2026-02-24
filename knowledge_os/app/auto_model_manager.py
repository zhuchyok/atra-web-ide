"""
Auto Model Manager для автоматической загрузки/выгрузки моделей на основе паттернов использования.
Анализирует время дня и автоматически загружает соответствующие модели.
"""

import asyncio
import logging
import os
from datetime import datetime, time
from enum import Enum
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Импорты с fallback
try:
    from model_memory_manager import ModelMemoryManager, get_memory_manager
except ImportError:
    get_memory_manager = None
    ModelMemoryManager = None


class TimeOfDay(Enum):
    """Время дня для выбора моделей"""

    MORNING = "morning"  # 6:00 - 12:00
    AFTERNOON = "afternoon"  # 12:00 - 18:00
    EVENING = "evening"  # 18:00 - 22:00
    NIGHT = "night"  # 22:00 - 6:00


class AutoModelManager:
    """
    Автономный менеджер моделей с умной загрузкой по времени.
    Автоматически загружает/выгружает модели на основе паттернов использования.
    """

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.memory_manager = get_memory_manager(ollama_url) if get_memory_manager else None

        # Конфигурация моделей по времени дня
        self.model_configs = {
            TimeOfDay.MORNING: {
                "priority_models": ["qwen2.5-coder:32b"],  # MLX модель (Mac Studio) - Coding утром
                "fallback_models": ["phi3.5:3.8b"],  # Ollama модель (Mac Studio)
                "unload_models": ["qwen2.5-coder:32b"],
            },
            TimeOfDay.AFTERNOON: {
                "priority_models": [
                    "qwen2.5-coder:32b",
                    "phi3.5:3.8b",
                ],  # MLX + Ollama модели (Mac Studio)
                "fallback_models": ["tinyllama:1.1b-chat-v1.0-q4_0"],
                "unload_models": [],
            },
            TimeOfDay.EVENING: {
                "priority_models": ["phi3.5:3.8b", "qwen2.5-coder:32b"],
                "fallback_models": ["phi3:mini-4k-instruct-q4_k_m"],
                "unload_models": [],
            },
            TimeOfDay.NIGHT: {
                "priority_models": ["tinyllama:1.1b-chat-v1.0-q4_0"],  # Только легкие модели ночью
                "fallback_models": [],
                "unload_models": ["qwen2.5-coder:32b"],
            },
        }

        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

    def get_time_of_day(self) -> TimeOfDay:
        """Определяет текущее время дня"""
        current_hour = datetime.now().hour

        if 6 <= current_hour < 12:
            return TimeOfDay.MORNING
        elif 12 <= current_hour < 18:
            return TimeOfDay.AFTERNOON
        elif 18 <= current_hour < 22:
            return TimeOfDay.EVENING
        else:
            return TimeOfDay.NIGHT

    async def get_loaded_models(self) -> List[str]:
        """Получить список загруженных моделей"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return [model["name"] for model in data.get("models", [])]
        except Exception as e:
            logger.warning(f"Ошибка получения списка моделей: {e}")
        return []

    async def load_model(self, model_name: str) -> bool:
        """Загрузить модель через Ollama API"""
        try:
            logger.info(f"🔄 Загрузка модели {model_name}...")
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Загружаем модель через generate запрос
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": model_name, "prompt": "test", "stream": False},
                    timeout=60.0,
                )
                if response.status_code == 200:
                    logger.info(f"✅ Модель {model_name} загружена")
                    return True
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки модели {model_name}: {e}")
        return False

    async def unload_model(self, model_name: str) -> bool:
        """Выгрузить модель (пометить как неиспользуемую)"""
        if self.memory_manager:
            return await self.memory_manager.unload_model(model_name)
        return False

    async def optimize_models_for_time(self):
        """Оптимизирует набор моделей для текущего времени дня"""
        time_of_day = self.get_time_of_day()
        config = self.model_configs[time_of_day]

        logger.info(f"🕐 Текущее время дня: {time_of_day.value}")

        loaded_models = await self.get_loaded_models()

        # Выгружаем модели, которые не нужны в это время
        for model_to_unload in config.get("unload_models", []):
            if model_to_unload in loaded_models:
                logger.info(
                    f"⏰ Выгружаем модель {model_to_unload} (не нужна в {time_of_day.value})"
                )
                await self.unload_model(model_to_unload)

        # Загружаем приоритетные модели, если их нет
        for priority_model in config.get("priority_models", []):
            if priority_model not in loaded_models:
                # Проверяем доступную память перед загрузкой
                if self.memory_manager:
                    available_mb = await self.memory_manager.get_available_memory_mb()
                    if available_mb < 200:  # MIN_FREE_MEMORY_MB
                        logger.warning(
                            f"⚠️ Недостаточно памяти для загрузки {priority_model} ({available_mb}MB)"
                        )
                        continue

                logger.info(
                    f"⏰ Загружаем приоритетную модель {priority_model} для {time_of_day.value}"
                )
                await self.load_model(priority_model)

    async def monitor_and_optimize(self, check_interval: int = 3600):
        """Мониторинг и автоматическая оптимизация моделей"""
        self._running = True
        logger.info("🔍 Запущен автономный мониторинг моделей")

        last_time_of_day = None

        while self._running:
            try:
                current_time_of_day = self.get_time_of_day()

                # Оптимизируем только при смене времени дня
                if current_time_of_day != last_time_of_day:
                    logger.info(
                        f"🔄 Смена времени дня: {last_time_of_day.value if last_time_of_day else 'start'} -> {current_time_of_day.value}"
                    )
                    await self.optimize_models_for_time()
                    last_time_of_day = current_time_of_day

                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.error(f"Ошибка в мониторинге моделей: {e}")
                await asyncio.sleep(check_interval)

    def start_monitoring(self, check_interval: int = 3600):
        """Запустить мониторинг моделей"""
        if not self._running:
            self._monitor_task = asyncio.create_task(self.monitor_and_optimize(check_interval))

    def stop_monitoring(self):
        """Остановить мониторинг моделей"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()


# Глобальный экземпляр
_auto_model_manager: Optional[AutoModelManager] = None


def get_auto_model_manager(ollama_url: str = "http://localhost:11434") -> AutoModelManager:
    """Получить глобальный экземпляр AutoModelManager"""
    global _auto_model_manager
    if _auto_model_manager is None:
        _auto_model_manager = AutoModelManager(ollama_url)
    return _auto_model_manager
