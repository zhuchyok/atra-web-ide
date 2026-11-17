import asyncio
import logging
import os
import time
from typing import Dict, List, Optional

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
        # [v173] Hands live on 11437 — never warm phi onto brain 11434.
        self.hands_url = (
            os.getenv("OLLAMA_HANDS_URL")
            or os.getenv("OLLAMA_HANDS_BASE_URL")
            or "http://localhost:11437"
        ).rstrip("/")
        self.last_used_model = None
        self.preloaded_models = set()
        self._lock = asyncio.Lock()

    def _warmup_base_url(self, model_name: str, target_url: Optional[str] = None) -> str:
        """Route phi/nomic warmup to hands; other models keep caller/brain URL."""
        if target_url:
            return target_url.rstrip("/")
        key = (model_name or "").lower()
        if "phi3.5" in key or "nomic" in key:
            return self.hands_url
        return self.ollama_url.rstrip("/")

    async def warm_up_model(
        self, model_name: str, keep_alive: int = -1, *, target_url: Optional[str] = None
    ):
        """
        Отправляет пустой запрос для загрузки модели в память.
        phi → OLLAMA_HANDS_URL (11437). Wisdom/coder/lfm на brain 11434 не грузим.
        """
        try:
            from available_models_scanner import _skip_as_ollama_hands
        except Exception:
            from app.available_models_scanner import _skip_as_ollama_hands

        if _skip_as_ollama_hands(model_name) or "lfm" in (model_name or "").lower():
            logger.debug("[INFERENCE] skip warmup of %s (brain/coder/heavy)", model_name)
            return

        base = self._warmup_base_url(model_name, target_url)

        async with self._lock:
            if model_name in self.preloaded_models:
                return

            logger.info("🔥 [INFERENCE] Упреждающая загрузка модели: %s @ %s", model_name, base)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{base}/api/generate",
                        json={
                            "model": model_name,
                            "prompt": " ",
                            "stream": False,
                            "keep_alive": keep_alive,
                        },
                        timeout=aiohttp.ClientTimeout(total=60),
                    ) as resp:
                        if resp.status == 200:
                            self.preloaded_models.add(model_name)
                            logger.info("✅ [INFERENCE] Модель %s готова к работе", model_name)
            except Exception as e:
                logger.warning("⚠️ [INFERENCE] Ошибка прогрева модели %s: %s", model_name, e)

    async def predict_and_preload(self, current_category: str):
        """Держит штатные руки phi3.5 на 11437 (не на brain 11434)."""
        models_to_preload = ["phi3.5:3.8b"]
        for model in models_to_preload:
            asyncio.create_task(self.warm_up_model(model, keep_alive=-1, target_url=self.hands_url))

    def reset_cache(self):
        self.preloaded_models.clear()


_optimizer = None


def get_inference_optimizer():
    global _optimizer
    if _optimizer is None:
        _optimizer = InferenceOptimizer()
    return _optimizer
