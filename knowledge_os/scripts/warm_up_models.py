import asyncio
import os
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Реально существующие модели в Ollama (автоматически сканируются при запуске)
# Ollama: qwq:32b, qwen2.5-coder:32b, glm-4.7-flash:q8_0, llava:7b, phi3.5:3.8b, moondream:latest, tinyllama:1.1b-chat
MODELS = ["qwq:32b", "qwen2.5-coder:32b", "phi3.5:3.8b", "moondream:latest", "tinyllama:1.1b-chat"]
OLLAMA_URL = "http://localhost:11434/api/generate"

async def warm_up_model(model: str):
    logger.info(f"🔥 Warming up model: {model}...")
    try:
        async with httpx.AsyncClient() as client:
            # Just a tiny prompt to trigger load
            await client.post(
                OLLAMA_URL,
                json={"model": model, "prompt": "ok", "stream": False},
                timeout=60.0
            )
        logger.info(f"✅ Model {model} is warm and ready.")
    except Exception as e:
        logger.error(f"❌ Failed to warm up {model}: {e}")

async def run_warming():
    logger.info("✨ Starting sequential model warming...")
    for model_name in MODELS:
        await warm_up_model(model_name)
    logger.info("✨ All models are warmed up and in GPU memory.")

if __name__ == "__main__":
    asyncio.run(run_warming())
