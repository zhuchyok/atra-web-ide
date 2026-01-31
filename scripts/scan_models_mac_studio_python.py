#!/usr/bin/env python3
"""
Полное сканирование всех моделей на Mac Studio M4 Max
Запускайте этот скрипт на Mac Studio для проверки всех установленных моделей
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

def get_ollama_models() -> Tuple[List[Dict], float]:
    """Получает список Ollama моделей и их общий размер"""
    models = []
    total_size = 0
    
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')[1:]  # Пропускаем заголовок
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[0]
                        size_str = parts[2] if len(parts) > 2 else "0"
                        # Парсим размер
                        size_gb = 0
                        if 'GB' in size_str:
                            size_gb = float(size_str.replace('GB', '').strip())
                        elif 'MB' in size_str:
                            size_gb = float(size_str.replace('MB', '').strip()) / 1024
                        models.append({
                            'name': name,
                            'size': size_str,
                            'size_gb': size_gb
                        })
                        total_size += size_gb
    except Exception as e:
        print(f"⚠️  Ошибка получения Ollama моделей: {e}")
    
    return models, total_size


def get_mlx_models_hf_cache() -> Tuple[List[Dict], float]:
    """Получает список MLX моделей из HuggingFace кеша"""
    models = []
    total_size = 0
    
    hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
    if not hf_cache.exists():
        return models, total_size
    
    mlx_dirs = [d for d in hf_cache.iterdir() if d.is_dir() and "mlx-community" in d.name]
    
    for mlx_dir in mlx_dirs:
        model_name = mlx_dir.name.replace("models--", "").replace("--", "/")
        try:
            size = sum(f.stat().st_size for f in mlx_dir.rglob('*') if f.is_file())
            size_gb = size / (1024**3)
            models.append({
                'name': model_name,
                'path': str(mlx_dir),
                'size_gb': size_gb
            })
            total_size += size_gb
        except Exception as e:
            print(f"⚠️  Ошибка обработки {model_name}: {e}")
    
    return models, total_size


def get_mlx_models_dir() -> Tuple[List[Dict], float]:
    """Получает список MLX моделей из ~/.mlx_models"""
    models = []
    total_size = 0
    
    mlx_dir = Path.home() / ".mlx_models"
    if not mlx_dir.exists():
        return models, total_size
    
    model_dirs = [d for d in mlx_dir.iterdir() if d.is_dir()]
    
    for model_dir in model_dirs:
        try:
            size = sum(f.stat().st_size for f in model_dir.rglob('*') if f.is_file())
            size_gb = size / (1024**3)
            models.append({
                'name': model_dir.name,
                'path': str(model_dir),
                'size_gb': size_gb
            })
            total_size += size_gb
        except Exception as e:
            print(f"⚠️  Ошибка обработки {model_dir.name}: {e}")
    
    return models, total_size


def check_ollama_api() -> bool:
    """Проверяет доступность Ollama API"""
    try:
        import httpx
        response = httpx.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        try:
            import urllib.request
            response = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
            return response.status == 200
        except:
            return False


def check_mlx_available() -> bool:
    """Проверяет доступность MLX"""
    try:
        import mlx.core as mx
        return True
    except ImportError:
        return False


def main():
    print("=" * 70)
    print("🔍 ПОЛНОЕ СКАНИРОВАНИЕ МОДЕЛЕЙ НА MAC STUDIO M4 MAX")
    print("=" * 70)
    print()
    
    # 1. Ollama модели
    print("📦 OLLAMA МОДЕЛИ:")
    print("-" * 70)
    ollama_models, ollama_total = get_ollama_models()
    if ollama_models:
        for model in ollama_models:
            print(f"  ✅ {model['name']:40} {model['size']:>10}")
        print(f"\n  Общий размер Ollama: {ollama_total:.2f} GB")
    else:
        print("  ⚠️  Ollama модели не найдены")
    
    print()
    print()
    
    # 2. MLX модели в HuggingFace кеше
    print("🍎 MLX МОДЕЛИ (HuggingFace кеш):")
    print("-" * 70)
    mlx_hf_models, mlx_hf_total = get_mlx_models_hf_cache()
    if mlx_hf_models:
        for model in mlx_hf_models:
            print(f"  ✅ {model['name']:50} {model['size_gb']:>6.2f} GB")
        print(f"\n  Общий размер MLX (HF cache): {mlx_hf_total:.2f} GB")
    else:
        print("  ⚠️  MLX модели не найдены в HuggingFace кеше")
    
    print()
    print()
    
    # 3. MLX модели в ~/.mlx_models
    print("📁 MLX МОДЕЛИ (стандартная директория ~/.mlx_models):")
    print("-" * 70)
    mlx_dir_models, mlx_dir_total = get_mlx_models_dir()
    if mlx_dir_models:
        for model in mlx_dir_models:
            print(f"  ✅ {model['name']:50} {model['size_gb']:>6.2f} GB")
        print(f"\n  Общий размер MLX (~/.mlx_models): {mlx_dir_total:.2f} GB")
    else:
        print("  ⚠️  Директория ~/.mlx_models не существует или пуста")
    
    print()
    print()
    
    # 4. Проверка сервисов
    print("🌐 ПРОВЕРКА СЕРВИСОВ:")
    print("-" * 70)
    ollama_api = check_ollama_api()
    print(f"  Ollama API (localhost:11434): {'✅ Доступен' if ollama_api else '❌ Недоступен'}")
    mlx_available = check_mlx_available()
    print(f"  MLX библиотека: {'✅ Установлена' if mlx_available else '❌ Не установлена'}")
    
    print()
    print()
    
    # 5. Общая статистика
    print("💾 ОБЩАЯ СТАТИСТИКА:")
    print("-" * 70)
    total_size = ollama_total + mlx_hf_total + mlx_dir_total
    print(f"  Ollama модели:        {ollama_total:>8.2f} GB")
    print(f"  MLX (HF cache):       {mlx_hf_total:>8.2f} GB")
    print(f"  MLX (~/.mlx_models):  {mlx_dir_total:>8.2f} GB")
    print(f"  {'-' * 30}")
    print(f"  ИТОГО:                {total_size:>8.2f} GB")
    
    print()
    print("=" * 70)
    print("✅ Сканирование завершено!")
    print()
    print("📋 Сохраните этот отчет для справки")
    print("=" * 70)


if __name__ == "__main__":
    main()

