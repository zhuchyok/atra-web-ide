"""
Model Availability Checker - verifies that a model responds (optional health check).

Uses ModelRegistry (available_models_scanner) for the list; can optionally ping Ollama/MLX
to confirm the model is actually available before assigning a task.
"""

import logging
from typing import Optional, Tuple

from .model_registry import ModelRegistry

logger = logging.getLogger(__name__)


class ModelAvailabilityChecker:
    """
    Checks model availability. Uses ModelRegistry for scanning; optionally verifies
    that the service (Ollama/MLX) responds.
    """

    def __init__(self, registry: Optional[ModelRegistry] = None):
        self._registry = registry or ModelRegistry()

    async def is_available(self, category: str, priority: str = "mlx") -> bool:
        """Return True if a model is available for the category."""
        model = await self._registry.get_available_model(category, priority=priority)
        return model is not None

    async def get_available_model(self, category: str, priority: str = "mlx") -> Optional[str]:
        """Return model name (e.g. mlx:qwen2.5-coder:32b) or None."""
        return await self._registry.get_available_model(category, priority=priority)

    async def check_service_responds(self, url: str, timeout: float = 3.0) -> bool:
        """Return True if the service at url responds (e.g. /api/tags or /health)."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=timeout) as client:
                for path in ("/api/tags", "/health", "/"):
                    try:
                        r = await client.get(f"{url.rstrip('/')}{path}")
                        if r.status_code in (200, 429):
                            return True
                    except Exception:
                        continue
            return False
        except ImportError:
            return False
        except Exception as e:
            logger.debug("check_service_responds %s: %s", url, e)
            return False
