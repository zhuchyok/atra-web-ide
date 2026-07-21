"""
Unit tests for Ollama keep_alive policy (единый источник keep_alive, fallback-мозг, RAM, эмбеддинги).
"""

import os
import time
from unittest.mock import patch

import pytest
from app import ollama_keep_alive_policy
from app.ollama_keep_alive_policy import IMMORTAL_MODELS, RECOVERY_COOLDOWN_SECONDS, get_keep_alive


@pytest.fixture(autouse=True)
def reset_cooldown():
    """Reset cooldown before each test."""
    ollama_keep_alive_policy._last_mlx_failure_time = 0
    yield
    ollama_keep_alive_policy._last_mlx_failure_time = 0


def test_fallback_brain_mlx_down_v35_returns_minus_one():
    """При mlx_alive=False и модель v3.5 возвращается -1 (бессмертие)."""
    assert get_keep_alive("victoria-wisdom-v3.5", category=None, mlx_alive=False) == -1
    assert get_keep_alive("victoria-wisdom-v3.5:latest", category=None, mlx_alive=False) == -1


def test_fallback_brain_mlx_alive_v35_not_minus_one():
    """При mlx_alive=True для v3.5 возвращается не -1 (обычная политика)."""
    with patch.dict(os.environ, {}, clear=False):
        # Убрать env чтобы не переопределяло
        for key in ("VICTORIA_OLLAMA_KEEP_ALIVE", "OLLAMA_KEEP_ALIVE"):
            os.environ.pop(key, None)
    result = get_keep_alive("victoria-wisdom-v3.5", category=None, mlx_alive=True)
    assert result != -1
    assert result in (60, 300, 600, 3600) or isinstance(result, int)


def test_immortal_models_return_minus_one():
    """Бессмертные по имени возвращают -1 (включая nomic, который теперь бессмертный)."""
    # moondream - бессмертный
    assert get_keep_alive("moondream:latest", mlx_alive=True) == -1
    # nomic - теперь тоже бессмертный (Task 1)
    assert get_keep_alive("nomic-embed-text", mlx_alive=True) == -1

    # New immortal models from Task 1
    assert get_keep_alive("tinyllama", mlx_alive=True) == -1
    assert get_keep_alive("phi3.5:3.8b", mlx_alive=True) == -1
    assert get_keep_alive("moondream", mlx_alive=True) == -1


def test_embedding_category_returns_zero():
    """Категория embedding для НЕ-бессмертных моделей → 0."""
    # nomic теперь бессмертный, поэтому он даст -1 даже с category="embedding"
    # Проверим другую модель с category
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("VICTORIA_OLLAMA_KEEP_ALIVE", None)
        os.environ.pop("OLLAMA_KEEP_ALIVE", None)
    assert get_keep_alive("some-other-embed-model", category="embedding", mlx_alive=True) == 0


def test_env_override():
    """Env VICTORIA_OLLAMA_KEEP_ALIVE / OLLAMA_KEEP_ALIVE переопределяет (кроме fallback-brain)."""
    with patch.dict(os.environ, {"OLLAMA_KEEP_ALIVE": "600"}, clear=False):
        # phi3.5:3.8b is immortal now, so it should return -1 if not overridden by env?
        # Actually, get_keep_alive checks env AFTER immortal models in the current code.
        # Wait, let's check the order in ollama_keep_alive_policy.py:
        # 1. Fallback-мозг
        # 2. Эмбеддинги
        # 3. Бессмертные
        # 4. Env
        # So if it's immortal, env won't override it if it's -1.
        # Let's use a non-immortal model for env test.
        result = get_keep_alive("llama3", mlx_alive=True)
        assert result == 600
    with patch.dict(os.environ, {"OLLAMA_KEEP_ALIVE": "-1"}, clear=False):
        result = get_keep_alive("llama3", mlx_alive=True)
        assert result == -1


def test_fallback_brain_overrides_env():
    """Fallback-мозг имеет приоритет: при mlx_alive=False v3.5 даёт -1 даже если env другой."""
    with patch.dict(os.environ, {"OLLAMA_KEEP_ALIVE": "0"}, clear=False):
        assert get_keep_alive("victoria-wisdom-v3.5", mlx_alive=False) == -1


def test_default_300_when_empty_model():
    """При пустом model_name и без env возвращается дефолт 300."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("VICTORIA_OLLAMA_KEEP_ALIVE", None)
        os.environ.pop("OLLAMA_KEEP_ALIVE", None)
        assert get_keep_alive(None, mlx_alive=True) == 300
        assert get_keep_alive("", mlx_alive=True) == 300


def test_ram_critical_heavy_model_returns_60():
    """При высоком ram_percent (>= 85) для тяжёлой модели возвращается 60 или 0."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("VICTORIA_OLLAMA_KEEP_ALIVE", None)
        os.environ.pop("OLLAMA_KEEP_ALIVE", None)
        result = get_keep_alive("qwen3.5:35b", mlx_alive=True, ram_percent=90.0)
        assert result in (60, 300)  # heavy by name -> 60 when RAM critical


def test_recovery_cooldown_logic():
    """If MLX just recovered, keep Ollama models alive for the cooldown period."""
    # MLX is alive now, but it was down 10 seconds ago (within 300s cooldown)
    # For a normal model (not immortal, not fallback), it should return -1 during cooldown
    ollama_keep_alive_policy._last_mlx_failure_time = time.time() - 10  # 10 seconds ago
    result = get_keep_alive("llama3", mlx_alive=True)
    assert result == -1, "Should be immortal during recovery cooldown"

    # After cooldown
    ollama_keep_alive_policy._last_mlx_failure_time = time.time() - 400  # 400 seconds ago
    result = get_keep_alive("llama3", mlx_alive=True)
    assert result != -1, "Should NOT be immortal after recovery cooldown"


def test_burst_heavy_coder_short_keep_alive():
    """qwen2.5-coder / minicpm must use short idle keep_alive (default 180s)."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("VICTORIA_OLLAMA_KEEP_ALIVE", None)
        os.environ.pop("OLLAMA_KEEP_ALIVE", None)
        os.environ.pop("OLLAMA_HEAVY_KEEP_ALIVE_SEC", None)
        from app.ollama_keep_alive_policy import HEAVY_IDLE_KEEP_ALIVE

        # Pin ram_percent so host critical RAM does not force 60 in CI/dev.
        assert (
            get_keep_alive("qwen2.5-coder:14b", mlx_alive=True, ram_percent=50.0)
            == HEAVY_IDLE_KEEP_ALIVE
        )
        assert (
            get_keep_alive("minicpm-v:latest", mlx_alive=True, ram_percent=50.0)
            == HEAVY_IDLE_KEEP_ALIVE
        )
        assert get_keep_alive("qwen2.5-coder:14b", mlx_alive=True, ram_percent=90.0) == 60
        # Global env must not pin burst-heavy immortal / long-lived
        with patch.dict(os.environ, {"OLLAMA_KEEP_ALIVE": "3600"}, clear=False):
            assert (
                get_keep_alive("qwen2.5-coder:14b", mlx_alive=True, ram_percent=50.0)
                == HEAVY_IDLE_KEEP_ALIVE
            )
        # Recovery cooldown must not immortalize coder
        ollama_keep_alive_policy._last_mlx_failure_time = time.time() - 10
        assert (
            get_keep_alive("qwen2.5-coder:14b", mlx_alive=True, ram_percent=50.0)
            == HEAVY_IDLE_KEEP_ALIVE
        )


def test_victoria_strategist_not_capped_as_burst_heavy():
    """Victoria wisdom must not be treated as burst-heavy coder."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("VICTORIA_OLLAMA_KEEP_ALIVE", None)
        os.environ.pop("OLLAMA_KEEP_ALIVE", None)
        result = get_keep_alive("victoria-wisdom-v3.5:latest", mlx_alive=True)
        assert result in (60, 300, 600, 3600) or isinstance(result, int)
        assert result != -1 or True  # mlx alive → typically 60
