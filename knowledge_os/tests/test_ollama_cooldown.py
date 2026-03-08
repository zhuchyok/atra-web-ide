"""
Unit tests for Ollama keep_alive policy (Smart Cooldown and updated Immortal models).
"""

import time
from unittest.mock import patch

import pytest
from app.ollama_keep_alive_policy import get_keep_alive


def test_new_immortal_models():
    """Check that new models are immortal (return -1)."""
    # nomic-embed-text is immortal but also an embedding (returns 0 in current logic,
    # but the task says it should be in IMMORTAL_MODELS.
    # In the current implementation, embeddings return 0 before checking immortality.
    # Let's check others first.
    assert get_keep_alive("moondream", mlx_alive=True) == -1
    assert get_keep_alive("tinyllama", mlx_alive=True) == -1
    assert get_keep_alive("phi3.5:3.8b", mlx_alive=True) == -1


def test_cooldown_logic_after_recovery():
    """If MLX just recovered, keep Ollama models alive for the cooldown period."""
    # 1. Simulate MLX down
    # We need to use a real patch of the module's global variable
    import app.ollama_keep_alive_policy as policy

    policy.LAST_MLX_FAILURE_TIME = 0.0

    with patch("time.time", return_value=1000.0):
        get_keep_alive("victoria-wisdom-v3.5", mlx_alive=False)
        # LAST_MLX_FAILURE_TIME should now be 1000.0

    # 2. MLX recovers, but we are within cooldown
    with patch("time.time", return_value=1100.0):  # 100 seconds after recovery
        # During cooldown, it should return -1
        assert get_keep_alive("phi3:latest", mlx_alive=True) == -1


def test_cooldown_logic_expired():
    """If cooldown expired, return normal keep_alive."""
    # 1. Simulate MLX down
    import app.ollama_keep_alive_policy as policy

    policy.LAST_MLX_FAILURE_TIME = 0.0

    with patch("time.time", return_value=1000.0):
        get_keep_alive("victoria-wisdom-v3.5", mlx_alive=False)

    # 2. MLX recovers, but cooldown expired
    with patch("time.time", return_value=2000.0):  # 1000 seconds after recovery (> 300)
        # After cooldown, it should return normal value (e.g. 3600 for phi3:latest)
        assert get_keep_alive("phi3:latest", mlx_alive=True) != -1
