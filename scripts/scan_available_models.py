#!/usr/bin/env python3
"""
Автоматическое сканирование доступных моделей в MLX и Ollama
Обновляет конфигурацию системы на основе реально установленных моделей
"""
import asyncio
import httpx
import json
import os
import sys
from typing import Dict, List, Set
from datetime import datetime

# Пути к конфигурационным файлам
MLX_URL = os.getenv('MLX_URL', 'http://localhost:11435')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
OUTPUT_FILE = os.getenv('MODELS_SCAN_OUTPUT', '/tmp/available_models.json')

async def scan_mlx_models() -> List[str]:
    """Сканирование моделей в MLX API Server"""
    models = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Проверяем /api/tags или /health
            try:
                response = await client.get(f"{MLX_URL}/api/tags", timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    if 'models' in data:
                        models = [m.get('name', '') for m in data['models'] if m.get('name')]
            except:
                # Пробуем /health
                try:
                    response = await client.get(f"{MLX_URL}/health", timeout=5.0)
                    if response.status_code == 200:
                        # Если есть список моделей в health
                        data = response.json()
                        if 'available_models' in data:
                            models = data['available_models']
                except:
                    pass
    except Exception as e:
        print(f"⚠️ Ошибка сканирования MLX: {e}")
    return models

async def scan_ollama_models() -> List[str]:
    """Сканирование моделей в Ollama"""
    models = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                if 'models' in data:
                    models = [m.get('name', '') for m in data['models'] if m.get('name')]
    except Exception as e:
        print(f"⚠️ Ошибка сканирования Ollama: {e}")
    return models

async def scan_all_models() -> Dict:
    """Сканирование всех доступных моделей"""
    print("🔍 Сканирование моделей...")

    mlx_models = await scan_mlx_models()
    ollama_models = await scan_ollama_models()

    result = {
        "timestamp": datetime.now().isoformat(),
        "mlx_models": sorted(mlx_models),
        "ollama_models": sorted(ollama_models),
        "all_models": sorted(set(mlx_models + ollama_models))
    }

    # Сохраняем результат
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✅ Найдено моделей:")
    print(f"   MLX: {len(mlx_models)}")
    print(f"   Ollama: {len(ollama_models)}")
    print(f"   Всего уникальных: {len(result['all_models'])}")
    print(f"📄 Результат сохранен в: {OUTPUT_FILE}")

    return result

if __name__ == '__main__':
    result = asyncio.run(scan_all_models())
    print("\n📊 Доступные модели:")
    print(f"MLX ({len(result['mlx_models'])}): {', '.join(result['mlx_models'])}")
    print(f"Ollama ({len(result['ollama_models'])}): {', '.join(result['ollama_models'])}")
