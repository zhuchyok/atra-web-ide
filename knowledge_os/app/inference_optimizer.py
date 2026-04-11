import asyncio
import logging
import os
import time
from typing import Optional, List, Dict

import aiohttp

logger = logging.getLogger(__name__)

class InferenceOptimizer:
    """
    Inference Optimizer (Singularity 23.2):
    Оптимизирует задержки инференса через упреждающую загрузку (Pre-loading)
    и управление горячим кэшем моделей.
    """

    def __init__(self, ollama_url: str = None):
        self.ollama_url = ollama_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.last_used_model = None
        self.preloaded_models = set()
        self._lock = asyncio.Lock()

    async def warm_up_model(self, model_name: str, keep_alive: int = 60):
        """
        Отправляет пустой запрос для загрузки модели в память.
        """
        async with self._lock:
            if model_name in self.preloaded_models:
                return

            logger.info(f"🔥 [INFERENCE] Упреждающая загрузка модели: {model_name}")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.ollama_url}/api/generate",
                        json={
                            "model": model_name,
                            "prompt": " ",
                            "stream": False,
                            "keep_alive": keep_alive
                        },
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as resp:
                        if resp.status == 200:
                            self.preloaded_models.add(model_name)
                            logger.info(f"✅ [INFERENCE] Модель {model_name} готова к работе")
            except Exception as e:
                logger.error(f"❌ [INFERENCE] Ошибка прогрева модели {model_name}: {e}")

    async def predict_and_preload(self, current_category: str):
        """
        Предсказывает следующую модель на основе текущей категории и загружает её.
        NOTE: Только легкие модели, НЕ phi3.5/qwen (дедлок Metal при выгрузке).
        """
        # Предзагрузка только лёгких моделей через Ollama
        predictions = {
            "reasoning": ["lfm2.5-thinking:1.2b"],
            "coding": ["lfm2.5-thinking:1.2b"],
            "general": ["lfm2.5-thinking:1.2b"],
        }
        
        models_to_preload = predictions.get(current_category, [])
        for model in models_to_preload:
            asyncio.create_task(self.warm_up_model(model, keep_alive=60))

    def reset_cache(self):
        self.preloaded_models.clear()

_optimizer = None

def get_inference_optimizer():
    global _optimizer
    if _optimizer is None:
        _optimizer = InferenceOptimizer()
    return _optimizer
