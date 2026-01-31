#!/usr/bin/env python3
"""
Скрипт для копирования mlx_api_server.py на Mac Studio
Запускать на Mac Studio: python3 scripts/copy_mlx_server_to_macstudio.py
"""

import os
import shutil

# Находим репозиторий (atra-web-ide или atra)
root = None
for d in [
    os.path.expanduser("~/Documents/atra-web-ide"),
    os.path.expanduser("~/Documents/dev/atra"),
    os.path.expanduser("~/atra"),
    os.path.expanduser("~/Documents/GITHUB/atra/atra"),
]:
    p = os.path.join(d, "knowledge_os", "docker-compose.yml") if "atra" in d else os.path.join(d, "docker-compose.yml")
    if os.path.exists(p) or os.path.exists(os.path.join(d, "knowledge_os", "app", "mlx_api_server.py")):
        root = d
        break

if not root:
    print("❌ Репозиторий не найден")
    exit(1)

api_file = os.path.join(root, "knowledge_os", "app", "mlx_api_server.py")
os.makedirs(os.path.dirname(api_file), exist_ok=True)

# Содержимое файла (полная версия)
content = '''"""
MLX API Server для Mac Studio M4 Max
FastAPI сервер для обслуживания запросов от агентов через MLX модели
"""

import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import os
from mlx_lm import load, generate
import sys

# Добавляем путь к mlx_router для импорта
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MLX Model Server", version="1.0.0")

# Кэш загруженных моделей
_models_cache = {}

# Конфигурация моделей (пути к MLX моделям)
MODEL_PATHS = {
    "default": os.path.expanduser("~/.mlx_models/Qwen2.5-Coder-32B-Instruct-Q8"),
}

# Можно также использовать переменную окружения
MLX_MODELS_DIR = os.getenv("MLX_MODELS_DIR", os.path.expanduser("~/.mlx_models"))


class GenerateRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    max_tokens: int = 512
    temperature: float = 0.7
    stream: bool = False


def get_model(model_key: str):
    """Получает или загружает модель"""
    if model_key in _models_cache:
        return _models_cache[model_key]
    
    model_path = MODEL_PATHS.get(model_key)
    if not model_path:
        model_path = os.path.join(MLX_MODELS_DIR, model_key)
    
    if not model_path or not os.path.exists(model_path):
        raise ValueError(f"Model {model_key} not found at {model_path}")
    
    logger.info(f"🔄 Загрузка модели: {model_key} из {model_path}")
    model, tokenizer = load(model_path)
    
    _models_cache[model_key] = {"model": model, "tokenizer": tokenizer}
    logger.info(f"✅ Модель загружена: {model_key}")
    return _models_cache[model_key]


@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "online",
        "server": "MLX Model Server",
        "device": "Mac Studio M4 Max",
        "models_loaded": len(_models_cache),
        "available_models": list(MODEL_PATHS.keys())
    }


@app.get("/api/tags")
async def list_models():
    """Список доступных моделей (совместимость с Ollama API)"""
    return {
        "models": [
            {"name": name, "model": name, "size": 0, "format": "mlx", "exists": os.path.exists(MODEL_PATHS.get(name, ""))}
            for name in MODEL_PATHS.keys()
        ]
    }


@app.post("/api/generate")
async def generate_text(request: GenerateRequest):
    """Генерация текста (совместимость с Ollama API)"""
    try:
        model_key = request.model or "default"
        model_data = get_model(model_key)
        model, tokenizer = model_data["model"], model_data["tokenizer"]
        if request.stream:
            return StreamingResponse(
                generate_stream(model, tokenizer, request.prompt, request.max_tokens),
                media_type="application/json"
            )
        loop = asyncio.get_event_loop()
        response_text = await loop.run_in_executor(
            None,
            lambda: generate(model, tokenizer, prompt=request.prompt, max_tokens=request.max_tokens)
        )
        return {"model": model_key, "response": response_text, "done": True}
    except Exception as e:
        logger.error(f"❌ Ошибка генерации: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def generate_stream(model, tokenizer, prompt: str, max_tokens: int):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens))
    for char in response:
        yield json.dumps({"response": char, "done": False}) + "\\n"
    yield json.dumps({"response": "", "done": True}) + "\\n"


@app.get("/api/models/{model_name}")
async def get_model_info(model_name: str):
    if model_name not in MODEL_PATHS:
        raise HTTPException(status_code=404, detail="Model not found")
    p = MODEL_PATHS[model_name]
    return {"name": model_name, "path": p, "exists": os.path.exists(p), "loaded": model_name in _models_cache}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=11434)
'''

if os.path.exists(api_file):
    os.remove(api_file)
    print("🗑️  Старый файл удален")

with open(api_file, 'w', encoding='utf-8') as f:
    f.write(content)

import py_compile
try:
    py_compile.compile(api_file, doraise=True)
    print(f"✅ Файл создан и корректен: {api_file}")
except py_compile.PyCompileError as e:
    print(f"❌ Ошибка синтаксиса: {e}")
    exit(1)

print("\n🚀 Запуск:")
print(f"   cd {root}")
print("   export PYTHONPATH=\"$(pwd):$PYTHONPATH\"")
print("   python3 -m uvicorn knowledge_os.app.mlx_api_server:app --host 0.0.0.0 --port 11434")
