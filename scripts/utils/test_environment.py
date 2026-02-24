#!/usr/bin/env python3
"""
Тесты для environment.py
Проверка корректности определения окружения
"""

import os
import sys
from pathlib import Path

# Настраиваем пути перед импортом
_project_root = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(_project_root))

from scripts.utils.environment import (
    is_docker,
    get_database_url,
    get_mlx_api_url,
    get_ollama_url,
    reset_cache,
)

def test_is_docker():
    """Тест определения Docker окружения"""
    result = is_docker()
    assert isinstance(result, bool), "is_docker должна возвращать bool"
    print(f"✅ is_docker: {result}")

def test_get_database_url():
    """Тест получения DATABASE_URL"""
    url = get_database_url()
    assert "postgresql://" in url, "DATABASE_URL должен быть PostgreSQL URL"
    print(f"✅ get_database_url: {url.replace('secret', '***')}")

def test_get_mlx_api_url():
    """Тест получения MLX API URL"""
    url = get_mlx_api_url()
    assert url.startswith("http://"), "MLX API URL должен начинаться с http://"
    assert "11435" in url, "MLX API должен быть на порту 11435"
    print(f"✅ get_mlx_api_url: {url}")

def test_get_ollama_url():
    """Тест получения Ollama URL"""
    url = get_ollama_url()
    assert url.startswith("http://"), "Ollama URL должен начинаться с http://"
    assert "11434" in url, "Ollama должен быть на порту 11434"
    print(f"✅ get_ollama_url: {url}")

def test_reset_cache():
    """Тест сброса кэша"""
    result1 = is_docker()
    reset_cache()
    result2 = is_docker()
    # После сброса результат должен быть тот же (если окружение не изменилось)
    assert isinstance(result2, bool), "После reset_cache is_docker должна возвращать bool"
    print(f"✅ reset_cache работает")

if __name__ == "__main__":
    print("🧪 ТЕСТИРОВАНИЕ environment.py")
    print("=" * 60)

    try:
        test_is_docker()
        test_get_database_url()
        test_get_mlx_api_url()
        test_get_ollama_url()
        test_reset_cache()

        print("=" * 60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    except AssertionError as e:
        print(f"❌ ОШИБКА: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ НЕОЖИДАННАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
