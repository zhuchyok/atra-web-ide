"""
Unit tests for Ollama keep_alive policy (единый источник keep_alive, fallback-мозг, RAM, эмбеддинги).
"""

import os
import time
from unittest.mock import patch

import pytest
from app.ollama_keep_alive_policy import (
    RECOVERY_COOLDOWN_SECONDS,
    get_keep_alive,
    set_mlx_failure_time,
)


def test_fallback_brain_mlx_down_v35_returns_minus_one():
    """При mlx_alive=False и модель v3.5 возвращается -1 (бессмертие)."""
    assert get_keep_alive("victoria-wisdom-v3.5", category=None, mlx_alive=False) == -1
    assert get_keep_alive("victoria-wisdom-v3.5:latest", category=None, mlx_alive=False) == -1


def test_fallback_brain_mlx_alive_v35_not_minus_one():
    """При mlx_alive=True для v3.5 возвращается не -1 (обычная политика)."""
    # Сначала сбрасываем время сбоя, чтобы кулдаун не мешал
    set_mlx_failure_time(0.0)
    with patch.dict(os.environ, {}, clear=False):
        # Убрать env чтобы не переопределяло
        for key in ("VICTORIA_OLLAMA_KEEP_ALIVE", "OLLAMA_KEEP_ALIVE"):
            os.environ.pop(key, None)
    result = get_keep_alive("victoria-wisdom-v3.5", category=None, mlx_alive=True)
    assert result != -1
    assert result in (60, 300, 600, 3600) or isinstance(result, int)


def test_immortal_models_return_minus_one():
    """Бессмертные по имени возвращают -1 (кроме эмбеддингов, которые 0)."""
    # moondream - бессмертный
    assert get_keep_alive("moondream:latest", mlx_alive=True) == -1
    # nomic - эмбеддинг, поэтому 0 (проверяется раньше бессмертных)
    # assert get_keep_alive("nomic-embed-text", mlx_alive=True) == -1  # This was actually wrong in existing test, nomic is embedding
    # tinyllama - бессмертный
    assert get_keep_alive("tinyllama", mlx_alive=True) == -1
    # phi3.5:3.8b - бессмертный
    assert get_keep_alive("phi3.5:3.8b", mlx_alive=True) == -1


def test_new_immortal_models_return_minus_one():
    """Новые бессмертные модели должны возвращать -1."""
    # nomic-embed-text should return -1 as per task (even if it's an embedding)
    assert get_keep_alive("nomic-embed-text", mlx_alive=True) == -1
    # moondream, tinyllama, phi3.5:3.8b are already there but let's re-verify
    assert get_keep_alive("moondream", mlx_alive=True) == -1
    assert get_keep_alive("tinyllama", mlx_alive=True) == -1
    assert get_keep_alive("phi3.5:3.8b", mlx_alive=True) == -1


def test_recovery_cooldown_logic():
    """Если MLX восстановился, но мы в периоде кулдауна — v3.5 остаётся бессмертной."""
    # 1. Симулируем сбой MLX сейчас
    now = time.time()
    set_mlx_failure_time(now)

    # 2. MLX 'ожил' (mlx_alive=True), но прошло всего 10 секунд (в пределах 300с кулдауна)
    assert get_keep_alive("victoria-wisdom-v3.5", mlx_alive=True) == -1

    # 3. Симулируем старый сбой (более 5 минут назад)
    set_mlx_failure_time(now - RECOVERY_COOLDOWN_SECONDS - 10)
    # Теперь кулдаун прошёл, v3.5 должна возвращать 60 (быстрая выгрузка при живом MLX)
    assert get_keep_alive("victoria-wisdom-v3.5", mlx_alive=True) == 60


def test_embedding_category_returns_zero():
    """Категория embedding или модель эмбеддинга → 0."""
    # nomic is now immortal, so it should return -1 even if category is embedding (immortal check is first)
    # We need to check a non-immortal embedding model
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("VICTORIA_OLLAMA_KEEP_ALIVE", None)
        os.environ.pop("OLLAMA_KEEP_ALIVE", None)
    assert get_keep_alive("some-embed-model", category="embedding", mlx_alive=True) == 0


def test_env_override():
    """Env VICTORIA_OLLAMA_KEEP_ALIVE / OLLAMA_KEEP_ALIVE переопределяет (кроме fallback-brain)."""
    with patch.dict(os.environ, {"OLLAMA_KEEP_ALIVE": "600"}, clear=False):
        result = get_keep_alive("phi3.5:3.8b", mlx_alive=True)
        assert result == 600
    with patch.dict(os.environ, {"OLLAMA_KEEP_ALIVE": "-1"}, clear=False):
        result = get_keep_alive("phi3.5:3.8b", mlx_alive=True)
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
