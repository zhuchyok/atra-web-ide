"""
MLX API Server для Mac Studio M4 Max
FastAPI сервер для обслуживания запросов от агентов через MLX модели
"""

import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
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
    "reasoning": os.path.expanduser("~/.mlx_models/DeepSeek-R1-Distill-Llama-70B-Q6"),
    "coding": os.path.expanduser("~/.mlx_models/Qwen2.5-Coder-32B-Instruct-Q8"),
    "fast": os.path.expanduser("~/.mlx_models/Phi-3.5-mini-instruct-Q4"),
    "tiny": os.path.expanduser("~/.mlx_models/TinyLlama-1.1B-Chat-Q4"),
    "qwen_3b": os.path.expanduser("~/.mlx_models/Qwen2.5-3B-Instruct-Q4"),
    "phi3_mini": os.path.expanduser("~/.mlx_models/Phi-3-mini-4k-instruct-Q4"),
    "default": os.path.expanduser("~/.mlx_models/Qwen2.5-Coder-32B-Instruct-Q8"),
}

# Можно также использовать переменную окружения
MLX_MODELS_DIR = os.getenv('MLX_MODELS_DIR', os.path.expanduser("~/.mlx_models"))

# Mapping категорий к моделям
CATEGORY_TO_MODEL = {
    "reasoning": "reasoning",
    "coding": "coding",
    "code": "coding",
    "fast": "fast",
    "tiny": "tiny",
    "default": "default"
}


class GenerateRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    category: Optional[str] = None
    max_tokens: int = 512
    temperature: float = 0.7
    stream: bool = False


def get_model(model_key: str):
    """Получает или загружает модель"""
    if model_key in _models_cache:
        return _models_cache[model_key]
    
    model_path = MODEL_PATHS.get(model_key)
    if not model_path:
        # Пробуем найти в MLX_MODELS_DIR
        model_path = os.path.join(MLX_MODELS_DIR, model_key)
    
    if not model_path or not os.path.exists(model_path):
        raise ValueError(f"Model {model_key} not found at {model_path}")
    
    logger.info(f"🔄 Загрузка модели: {model_key} из {model_path}")
    model, tokenizer = load(model_path)
    
    _models_cache[model_key] = {
        "model": model,
        "tokenizer": tokenizer
    }
    
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
            {
                "name": name,
                "model": name,
                "size": 0,
                "format": "mlx",
                "exists": os.path.exists(MODEL_PATHS.get(name, ""))
            }
            for name in MODEL_PATHS.keys()
        ]
    }


@app.post("/api/generate")
async def generate_text(request: GenerateRequest):
    """Генерация текста (совместимость с Ollama API)"""
    try:
        # Определяем модель
        if request.model:
            model_key = request.model
        elif request.category:
            model_key = CATEGORY_TO_MODEL.get(request.category, "default")
        else:
            model_key = "default"
        
        # Получаем модель
        model_data = get_model(model_key)
        model = model_data["model"]
        tokenizer = model_data["tokenizer"]
        
        # Генерация
        if request.stream:
            return StreamingResponse(
                generate_stream(model, tokenizer, request.prompt, request.max_tokens),
                media_type="application/json"
            )
        else:
            # Используем executor для async
            loop = asyncio.get_event_loop()
            response_text = await loop.run_in_executor(
                None,
                lambda: generate(model, tokenizer, prompt=request.prompt, max_tokens=request.max_tokens)
            )
            
            return {
                "model": model_key,
                "response": response_text,
                "done": True
            }
            
    except Exception as e:
        logger.error(f"❌ Ошибка генерации: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def generate_stream(model, tokenizer, prompt: str, max_tokens: int):
    """Streaming генерация"""
    # MLX не поддерживает streaming напрямую, эмулируем
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens)
    )
    
    # Разбиваем на токены для эмуляции streaming
    for char in response:
        yield json.dumps({"response": char, "done": False}) + "\n"
    
    yield json.dumps({"response": "", "done": True}) + "\n"


@app.get("/api/models/{model_name}")
async def get_model_info(model_name: str):
    """Информация о модели"""
    if model_name not in MODEL_PATHS:
        raise HTTPException(status_code=404, detail="Model not found")
    
    model_path = MODEL_PATHS[model_name]
    exists = os.path.exists(model_path)
    
    return {
        "name": model_name,
        "path": model_path,
        "exists": exists,
        "loaded": model_name in _models_cache
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("MLX_API_PORT", "11435"))
    uvicorn.run(app, host="0.0.0.0", port=port)

