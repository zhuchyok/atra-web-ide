"""
MLX Optimization: Quantization Profiles & Memory Management

Based on llama.cpp audit (9/10):
- Quantization profiles per use case (reasoning vs speed)
- GPU memory monitoring and thresholds
- Aggressive cleanup at critical levels
"""

import gc
import logging
from enum import Enum
from typing import TypedDict

import mlx.core as mx


class GPUMemoryStats(TypedDict):
    allocated_bytes: int
    max_bytes: int
    allocated_mb: float
    max_mb: float
    percent: float
    status: str


logger = logging.getLogger(__name__)


class QuantProfile(str, Enum):
    """Профили выбора модели MLX (ключи из mlx_api_server.MODEL_PATHS)."""

    REASONING = "reasoning"  # victoria-wisdom-30b — сложные задачи, рассуждения
    CODING = "coding"  # victoria-wisdom-30b — код, рефакторинг
    FAST = "fast"  # phi3.5-mini-4k — быстрые ответы
    DEFAULT = "default"  # victoria-wisdom-30b — по умолчанию


# Model registry by quantization profile (ключи из mlx_api_server.MODEL_PATHS / CATEGORY_TO_MODEL)
# См. knowledge_os/app/mlx_api_server.py: fast=phi3.5-mini-4k, victoria-wisdom-30b=exported_model
QUANT_PROFILE_MODELS = {
    QuantProfile.REASONING: "victoria-wisdom-30b",
    QuantProfile.CODING: "victoria-wisdom-30b",
    QuantProfile.FAST: "fast",
    QuantProfile.DEFAULT: "victoria-wisdom-30b",
}

# Memory thresholds (%)
MEMORY_WARNING_THRESHOLD = 85
MEMORY_CRITICAL_THRESHOLD = 98


def get_model_by_profile(profile: str = "default") -> str:
    """
    Get model path by quantization profile.

    Args:
        profile: One of "reasoning", "coding", "fast", "default"

    Returns:
        Model path string

    Example:
        >>> get_model_by_profile("reasoning")
        'victoria-wisdom-30b'
    """
    try:
        profile_enum = QuantProfile(profile.lower())
        return QUANT_PROFILE_MODELS[profile_enum]
    except (ValueError, KeyError):
        logger.warning(f"Unknown profile '{profile}', using default")
        return QUANT_PROFILE_MODELS[QuantProfile.DEFAULT]


def get_gpu_memory() -> GPUMemoryStats | None:
    """
    Get current GPU memory usage (Metal-specific).

    Returns:
        dict with memory stats or None if unavailable:
        {
            "allocated_bytes": int,
            "max_bytes": int,
            "allocated_mb": float,
            "max_mb": float,
            "percent": float (0-100),
            "status": str ("ok" | "warning" | "critical")
        }

    Based on llama.cpp ggml-metal-device.m patterns.
    """
    try:
        device = mx.metal.device()  # type: ignore[reportAttributeAccessIssue]

        # Try to get Metal device memory info
        allocated = getattr(device, "currentAllocatedSize", None)
        max_mem = getattr(device, "recommendedMaxWorkingSetSize", None)

        if allocated is not None and max_mem is not None and max_mem > 0:
            percent = (allocated / max_mem) * 100

            return {
                "allocated_bytes": int(allocated),
                "max_bytes": int(max_mem),
                "allocated_mb": round(allocated / (1024 * 1024), 2),
                "max_mb": round(max_mem / (1024 * 1024), 2),
                "percent": round(percent, 2),
                "status": (
                    "critical"
                    if percent > MEMORY_CRITICAL_THRESHOLD
                    else "warning"
                    if percent > MEMORY_WARNING_THRESHOLD
                    else "ok"
                ),
            }
    except Exception as e:
        logger.debug(f"Could not get GPU memory info: {e}")

    return None


def cleanup_if_critical() -> bool:
    """
    Perform aggressive memory cleanup if usage > 95%.

    Based on llama.cpp memory management patterns:
    - Clear Metal cache
    - Run Python garbage collection
    - Log cleanup action

    Returns:
        True if cleanup was performed, False otherwise
    """
    mem = get_gpu_memory()

    percent = mem.get("percent", 0.0) if mem else 0.0
    if mem and percent > MEMORY_CRITICAL_THRESHOLD:
        alloc_mb = mem.get("allocated_mb", 0.0)
        max_mb = mem.get("max_mb", 0.0)
        logger.warning(
            f"GPU memory critical: {percent:.1f}% "
            f"({alloc_mb:.0f}MB / {max_mb:.0f}MB). "
            f"Performing aggressive cleanup..."
        )

        # Clear MLX Metal cache
        try:
            mx.metal.clear_cache()
        except Exception as e:
            logger.error(f"Failed to clear Metal cache: {e}")

        # Run Python GC
        gc.collect()

        # Check memory after cleanup
        mem_after = get_gpu_memory()
        if mem_after:
            percent_after = mem_after.get("percent", 0.0)
            alloc_after = mem_after.get("allocated_mb", 0.0)
            logger.info(
                f"Cleanup complete. Memory: {percent_after:.1f}% "
                f"(freed {alloc_mb - alloc_after:.0f}MB)"
            )

        return True

    return False


def cleanup_if_warning() -> bool:
    """
    Perform light cleanup if usage > 80%.

    Returns:
        True if cleanup was performed, False otherwise
    """
    mem = get_gpu_memory()

    percent = mem.get("percent", 0.0) if mem else 0.0
    if mem and percent > MEMORY_WARNING_THRESHOLD:
        logger.info(f"GPU memory warning: {percent:.1f}%. Performing light cleanup...")

        # Just clear cache, no GC
        try:
            mx.metal.clear_cache()
        except Exception as e:
            logger.error(f"Failed to clear Metal cache: {e}")

        return True

    return False


def get_recommended_context_limit() -> int | None:
    """
    Get recommended context window limit based on available memory.

    Based on llama.cpp context management patterns.

    Returns:
        Recommended max context length or None if cannot determine
    """
    mem = get_gpu_memory()

    if not mem:
        return None

    # Rough heuristic: 1GB per 10K context for 30B model
    # Adjust based on available memory
    available_mb = mem.get("max_mb", 0.0) - mem.get("allocated_mb", 0.0)

    if available_mb < 1000:
        return 4096  # Conservative for low memory
    elif available_mb < 2000:
        return 8192
    elif available_mb < 4000:
        return 16384
    else:
        return 32768  # Max for high memory


# Metrics for monitoring
class MLXMetrics:
    """MLX inference metrics (llama.cpp-inspired)"""

    def __init__(self):
        self.load_time_ms = 0
        self.ttft_ms = 0  # Time to first token
        self.tokens_per_second = 0.0
        self.total_tokens = 0

    def to_dict(self) -> dict[str, float]:
        return {
            "load_time_ms": self.load_time_ms,
            "ttft_ms": self.ttft_ms,
            "tokens_per_second": self.tokens_per_second,
            "total_tokens": self.total_tokens,
        }
