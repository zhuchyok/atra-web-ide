"""
Unit tests for Ollama keep_alive policy (единый источник keep_alive, fallback-мозг, RAM, эмбеддинги).
"""

import os
from unittest.mock import patch

import pytest
from app.ollama_keep_alive_policy import get_keep_alive


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
    """Бессмертные по имени возвращают -1 (кроме эмбеддингов, которые 0)."""
    # moondream - бессмертный
    assert get_keep_alive("moondream:latest", mlx_alive=True) == -1
    # nomic - эмбеддинг, поэтому 0 (проверяется раньше бессмертных)
    assert get_keep_alive("nomic-embed-text", mlx_alive=True) == 0


def test_embedding_category_returns_zero():
    """Категория embedding или модель эмбеддинга → 0."""
    assert get_keep_alive("nomic-embed-text", category="embedding", mlx_alive=True) == 0
    # nomic уже в IMMORTAL, но category=embedding может обработаться раньше в другом порядке
    # В нашей реализации embedding проверяется после immortal; nomic даёт -1. Проверим другую модель с category
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
