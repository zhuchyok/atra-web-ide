"""
Model Registry - facade over available_models_scanner for task orchestration.

Does not duplicate scanning; delegates to available_models_scanner for MLX/Ollama lists.
Orchestrator and workers use this for model availability when assigning tasks.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from available_models_scanner import (
        get_available_models,
        pick_best_ollama,
        pick_best_mlx,
        pick_ollama_for_category,
        pick_mlx_for_category,
    )
except ImportError:
    try:
        from app.available_models_scanner import (
            get_available_models,
            pick_best_ollama,
            pick_best_mlx,
            pick_ollama_for_category,
            pick_mlx_for_category,
        )
    except ImportError:
        get_available_models = None
        pick_best_ollama = None
        pick_best_mlx = None
        pick_ollama_for_category = None
        pick_mlx_for_category = None


def _default_mlx_url() -> str:
    return os.getenv("MLX_API_URL", "http://localhost:11435")


def _default_ollama_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


class ModelRegistry:
    """
    Registry of available models (MLX and Ollama). Facade over available_models_scanner.
    Used by orchestrator and workers to choose models for tasks.
    """

    def __init__(self, mlx_url: Optional[str] = None, ollama_url: Optional[str] = None, ttl_sec: int = 120):
        self.mlx_url = mlx_url or _default_mlx_url()
        self.ollama_url = ollama_url or _default_ollama_url()
        self._ttl_sec = ttl_sec
        self._model_status: Dict[str, dict] = {}

    async def scan_models(self, force_refresh: bool = False) -> Tuple[List[str], List[str]]:
        """Return (mlx_models, ollama_models). Uses available_models_scanner."""
        if get_available_models is None:
            logger.warning("available_models_scanner not available")
            return ([], [])
        return await get_available_models(
            self.mlx_url,
            self.ollama_url,
            ttl_sec=self._ttl_sec,
            force_refresh=force_refresh,
        )

    async def get_available_model(self, category: str, priority: str = "mlx") -> Optional[str]:
        """
        Return an available model name for the given category.
        priority: "mlx" (prefer MLX) or "ollama".
        """
        mlx_list, ollama_list = await self.scan_models()
        if priority == "mlx" and mlx_list:
            model = pick_mlx_for_category(category, mlx_list) if pick_mlx_for_category else pick_best_mlx(mlx_list)
            if model:
                return f"mlx:{model}"
        if ollama_list:
            model = pick_ollama_for_category(category, ollama_list) if pick_ollama_for_category else pick_best_ollama(ollama_list)
            if model:
                return f"ollama:{model}"
        if priority == "ollama" and ollama_list:
            model = pick_ollama_for_category(category, ollama_list) if pick_ollama_for_category else pick_best_ollama(ollama_list)
            if model:
                return f"ollama:{model}"
        if mlx_list and pick_best_mlx:
            model = pick_best_mlx(mlx_list)
            if model:
                return f"mlx:{model}"
        return None

    async def get_mlx_and_ollama_best(self) -> Tuple[Optional[str], Optional[str]]:
        """Return (best_mlx_name, best_ollama_name) for generic use."""
        mlx_list, ollama_list = await self.scan_models()
        best_mlx = pick_best_mlx(mlx_list) if pick_best_mlx and mlx_list else None
        best_ollama = pick_best_ollama(ollama_list) if pick_best_ollama and ollama_list else None
        return (best_mlx, best_ollama)

    async def is_model_available(self, provider_model: str) -> bool:
        """
        Check if a model string like 'mlx:model_name' or 'ollama:model_name' is available.
        """
        if not provider_model or ":" not in provider_model:
            return False
        prefix, name = provider_model.split(":", 1)
        name = (name or "").strip()
        if not name:
            return False
        mlx_list, ollama_list = await self.scan_models()
        if prefix.lower() == "mlx":
            return name in (mlx_list or [])
        if prefix.lower() == "ollama":
            return name in (ollama_list or [])
        return False

    def get_model_status(self) -> Dict[str, dict]:
        """Return cached status dict (model_name -> {available, load}). May be empty until scan."""
        return dict(self._model_status)
