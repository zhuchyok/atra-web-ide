"""
Unit tests for Ollama keep_alive policy cooldown and immortal models.
"""

import time
from unittest.mock import patch

import app.ollama_keep_alive_policy as policy
import pytest
from app.ollama_keep_alive_policy import get_keep_alive


@pytest.fixture(autouse=True)
def reset_policy_state():
    """Reset the global state of the policy before each test."""
    policy._last_mlx_failure_time = 0.0
    yield


def test_immortal_models_return_minus_one_v2():
    """Verify that the specified immortal models return -1."""
    immortals = ["nomic-embed-text", "moondream", "tinyllama", "phi3.5:3.8b"]
    for model in immortals:
        result = get_keep_alive(model, mlx_alive=True)
        assert result == -1, f"Model {model} should return -1 as it is immortal"


def test_recovery_cooldown_logic():
    """
    Verify that models are kept alive during the recovery cooldown period
    after MLX comes back online.
    """
    model = "victoria-wisdom-v3.5"

    # 1. MLX is down -> policy tracks failure time
    with patch("time.time") as mock_time:
        now = 1700000000.0
        mock_time.return_value = now
        get_keep_alive(model, mlx_alive=False)
        assert policy._last_mlx_failure_time == now

    # 2. MLX just recovered (10 seconds ago) -> should return -1 (cooldown)
    with patch("time.time") as mock_time:
        now = 1700000000.0 + 10
        mock_time.return_value = now
        # _last_mlx_failure_time is already set to 1700000000.0

        result = get_keep_alive(model, mlx_alive=True)
        assert result == -1, "Should return -1 during recovery cooldown"

    # 3. MLX recovered long ago (600 seconds ago) -> should return normal keep_alive
    with patch("time.time") as mock_time:
        now = 1700000000.0 + 600
        mock_time.return_value = now

        result = get_keep_alive(model, mlx_alive=True)
        assert result != -1, "Should not return -1 after recovery cooldown"
        assert result == 60  # For victoria-wisdom-v3.5 when MLX is alive
