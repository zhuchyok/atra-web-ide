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

import mlx.core as mx

logger = logging.getLogger(__name__)


class QuantProfile(str, Enum):
    """Quantization profiles based on llama.cpp best practices"""

    REASONING = "reasoning"  # Q4_K_M - best quality/speed balance for complex tasks
    CODING = "coding"  # Q5_K_M - higher quality for code generation
    FAST = "fast"  # Q4_0 - maximum speed, lower quality
    DEFAULT = "default"  # Q8_0 - high quality, more memory


# Model registry by quantization profile
QUANT_PROFILE_MODELS = {
    QuantProfile.REASONING: "mlx-community/Qwen3-Coder-30B-Q4_K_M",
    QuantProfile.CODING: "mlx-community/Qwen3-Coder-30B-Q5_K_M",
    QuantProfile.FAST: "mlx-community/Qwen3-Coder-8B-Q4_0",
    QuantProfile.DEFAULT: "mlx-community/Qwen3-Coder-30B-Q8_0",
}

# Memory thresholds (%)
MEMORY_WARNING_THRESHOLD = 80
MEMORY_CRITICAL_THRESHOLD = 95


def get_model_by_profile(profile: str = "default") -> str:
    """
    Get model path by quantization profile.

    Args:
        profile: One of "reasoning", "coding", "fast", "default"

    Returns:
        Model path string

    Example:
        >>> get_model_by_profile("reasoning")
        'mlx-community/Qwen3-Coder-30B-Q4_K_M'
    """
    try:
        profile_enum = QuantProfile(profile.lower())
        return QUANT_PROFILE_MODELS[profile_enum]
    except (ValueError, KeyError):
        logger.warning(f"Unknown profile '{profile}', using default")
        return QUANT_PROFILE_MODELS[QuantProfile.DEFAULT]


def get_gpu_memory() -> dict[str, float] | None:
    """
    Get current GPU memory usage (Metal-specific).

    Returns:
        dict with memory stats or None if unavailable:
        {
            "allocated_bytes": int,
            "max_bytes": int,
            "allocated_mb": float,
            "max_mb": float,
            "percent": float (0-100)
        }

    Based on llama.cpp ggml-metal-device.m patterns.
    """
    try:
        device = mx.metal.device()

        # Try to get Metal device memory info
        allocated = getattr(device, "currentAllocatedSize", None)
        max_mem = getattr(device, "recommendedMaxWorkingSetSize", None)

        if allocated is not None and max_mem is not None and max_mem > 0:
            percent = (allocated / max_mem) * 100

            return {
                "allocated_bytes": allocated,
                "max_bytes": max_mem,
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

    if mem and mem["percent"] > MEMORY_CRITICAL_THRESHOLD:
        logger.warning(
            f"GPU memory critical: {mem['percent']:.1f}% "
            f"({mem['allocated_mb']:.0f}MB / {mem['max_mb']:.0f}MB). "
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
            logger.info(
                f"Cleanup complete. Memory: {mem_after['percent']:.1f}% "
                f"(freed {mem['allocated_mb'] - mem_after['allocated_mb']:.0f}MB)"
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

    if mem and mem["percent"] > MEMORY_WARNING_THRESHOLD:
        logger.info(f"GPU memory warning: {mem['percent']:.1f}%. Performing light cleanup...")

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
    available_mb = mem["max_mb"] - mem["allocated_mb"]

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
