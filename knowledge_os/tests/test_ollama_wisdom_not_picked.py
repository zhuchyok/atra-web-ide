"""Wisdom is MLX-only: Ollama pickers must not return victoria-wisdom*."""

from app.ai_core import _direct_ollama_fallback_models
from app.available_models_scanner import pick_best_ollama, pick_ollama_for_category
from app.local_router import OLLAMA_MODELS_FALLBACK


def test_pick_best_ollama_skips_wisdom():
    models = [
        "victoria-wisdom-24k:latest",
        "victoria-wisdom-v3.5:latest",
        "deepseek-r1:32b",
        "qwen3-coder:30b",
        "phi3.5:3.8b",
        "tinyllama:1.1b-chat",
    ]
    picked = pick_best_ollama(models)
    assert picked == "phi3.5:3.8b"


def test_pick_best_ollama_wisdom_only_returns_none():
    assert pick_best_ollama(["victoria-wisdom-v3.5:latest", "victoria-wisdom-24k", "deepseek-r1:32b"]) is None


def test_pick_ollama_for_category_skips_wisdom():
    models = [
        "victoria-wisdom-24k:latest",
        "victoria-wisdom-v3.5:latest",
        "deepseek-r1:32b",
        "qwen3-coder:30b",
        "phi3.5:3.8b",
        "tinyllama:1.1b-chat",
        "gemma3n:e4b",
    ]
    for category in ("default", "general", "reasoning", "coding"):
        picked = pick_ollama_for_category(category, models)
        assert picked == "phi3.5:3.8b", category


def test_pick_best_ollama_heavies_only_returns_none():
    assert pick_best_ollama(["deepseek-r1:32b", "qwen3-coder:30b", "qwen2.5-coder:14b"]) is None


def test_ollama_fallback_defaults_are_not_wisdom():
    for key, name in OLLAMA_MODELS_FALLBACK.items():
        assert "victoria-wisdom" not in str(name).lower(), (key, name)


def test_direct_ollama_fallback_models_are_light_hands():
    models = _direct_ollama_fallback_models("http://host.docker.internal:11434")
    assert models[0] == "phi3.5:3.8b"
    assert all("wisdom" not in m.lower() and "35b" not in m.lower() for m in models)
