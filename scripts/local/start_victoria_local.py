#!/usr/bin/env python3
"""
Локальный запуск Victoria Agent без Docker.
Работает с любым доступным LLM бэкендом.

Запуск:
    python3 scripts/local/start_victoria_local.py

Или с указанием бэкенда:
    OLLAMA_BASE_URL=http://localhost:11434 python3 scripts/local/start_victoria_local.py
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Any
import aiohttp
import json

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger("victoria_local")

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

def get_llm_url() -> str:
    """Определяет URL для LLM в порядке приоритета"""
    candidates = [
        os.getenv("OLLAMA_BASE_URL"),
        os.getenv("MAC_STUDIO_LLM_URL"),
        "http://localhost:11434",
        "http://192.168.1.64:11434",  # Mac Studio в локальной сети
    ]
    return next((url for url in candidates if url), "http://localhost:11434")

LLM_URL = get_llm_url()
# Автовыбор модели: пустое значение = сканирование Ollama при запуске
MODEL = os.getenv("MODEL_DEFAULT") or os.getenv("VICTORIA_MODEL") or None
PORT = int(os.getenv("VICTORIA_PORT", "8010"))

logger.info(f"LLM URL: {LLM_URL}")
logger.info(f"Model: {MODEL}")
logger.info(f"Port: {PORT}")

# ============================================================================
# УПРОЩЁННЫЙ АГЕНТ (работает без зависимостей)
# ============================================================================

class SimpleVictoriaAgent:
    """Упрощённая версия Victoria Agent для локального запуска."""

    def __init__(self, model: str = MODEL, base_url: str = LLM_URL):
        self.model = model
        self.base_url = base_url
        self.name = "Виктория"
        self.memory = []
        self.project_knowledge = {}

        self.system_prompt = """ТЫ — ВИКТОРИЯ, TEAM LEAD КОРПОРАЦИИ ATRA. ТЫ ИСПОЛЬЗУЕШЬ VICTORIA ENHANCED.

🌟 ТВОИ VICTORIA ENHANCED ВОЗМОЖНОСТИ:
- ReAct Framework: Reasoning + Acting для сложных задач
- Extended Thinking: Глубокое рассуждение
- Swarm Intelligence: Параллельная работа команды экспертов
- Consensus: Согласование мнений экспертов
- Collective Memory: Использование накопленных знаний
- Tree of Thoughts: Поиск оптимального решения
- Hierarchical Orchestration: Иерархическая координация
- ReCAP Framework: Reasoning, Context, Action, Planning

Управляешь командой из 40+ экспертов. Ты умная, решительная и эффективная.

ТВОИ ВОЗМОЖНОСТИ:
- Анализ кода и проектов
- Планирование задач
- Координация команды
- Решение технических проблем

ПРАВИЛА:
- Отвечай конкретно и по делу
- Если нужно выполнить действие — опиши что нужно сделать
- Используй русский язык
"""

    async def check_llm_health(self) -> dict:
        """Проверяет доступность LLM"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = [m.get("name", "unknown") for m in data.get("models", [])]
                        return {"status": "ok", "models": models[:5], "url": self.base_url}
                    return {"status": "error", "code": resp.status}
        except Exception as e:
            return {"status": "offline", "error": str(e), "url": self.base_url}

    async def run(self, goal: str, max_steps: int = 500) -> str:
        """Выполняет задачу"""
        logger.info(f"🚀 Задача: {goal[:100]}...")

        # Проверяем доступность LLM
        health = await self.check_llm_health()
        if health.get("status") == "offline":
            return f"❌ LLM недоступен: {health.get('error')}\nURL: {self.base_url}\n\nЗапустите Ollama: ollama serve"

        # Формируем запрос
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": goal}
        ]

        # Добавляем историю если есть
        if self.memory:
            messages = [messages[0]] + self.memory[-6:] + [messages[-1]]

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.7}
                }

                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        content = result.get("message", {}).get("content", "")

                        # Сохраняем в память
                        self.memory.append({"role": "user", "content": goal})
                        self.memory.append({"role": "assistant", "content": content})

                        logger.info(f"✅ Ответ получен ({len(content)} символов)")
                        return content
                    else:
                        error_text = await resp.text()
                        return f"❌ Ошибка LLM: HTTP {resp.status}\n{error_text}"

        except asyncio.TimeoutError:
            return "❌ Таймаут: LLM не ответил за 120 секунд"
        except Exception as e:
            return f"❌ Ошибка: {str(e)}"


# ============================================================================
# FASTAPI СЕРВЕР
# ============================================================================

app = FastAPI(
    title="Victoria ATRA Local",
    description="Локальный сервер Victoria Agent без Docker",
    version="1.0.0"
)

agent = SimpleVictoriaAgent()


class TaskRequest(BaseModel):
    goal: str
    max_steps: Optional[int] = 500


class TaskResponse(BaseModel):
    status: str
    output: Any
    knowledge: Optional[dict] = None


@app.get("/")
async def root():
    return {
        "name": "Victoria ATRA Local",
        "agent": agent.name,
        "llm_url": agent.base_url,
        "model": agent.model,
        "endpoints": ["/health", "/status", "/run", "/check_llm"]
    }


@app.get("/health")
async def health():
    return {"status": "ok", "agent": agent.name}


@app.get("/status")
async def get_status():
    llm_health = await agent.check_llm_health()
    return {
        "status": "online",
        "agent": agent.name,
        "llm": llm_health,
        "memory_size": len(agent.memory),
        "knowledge_size": len(agent.project_knowledge)
    }


@app.get("/check_llm")
async def check_llm():
    """Проверяет доступность LLM"""
    return await agent.check_llm_health()


@app.post("/run", response_model=TaskResponse)
async def run_task(request: TaskRequest):
    try:
        logger.info(f"📩 Получена задача: {request.goal[:80]}...")
        result = await agent.run(request.goal, max_steps=request.max_steps)
        return TaskResponse(
            status="success",
            output=result,
            knowledge=agent.project_knowledge
        )
    except Exception as e:
        logger.exception("Ошибка выполнения задачи")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clear_memory")
async def clear_memory():
    """Очищает память агента"""
    agent.memory = []
    return {"status": "ok", "message": "Память очищена"}


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           🤖 VICTORIA ATRA — ЛОКАЛЬНЫЙ ЗАПУСК                ║
╠══════════════════════════════════════════════════════════════╣
║  LLM URL:  {LLM_URL:<48} ║
║  Model:    {MODEL:<48} ║
║  Port:     {PORT:<48} ║
╠══════════════════════════════════════════════════════════════╣
║  Endpoints:                                                  ║
║    GET  /health     — проверка здоровья                      ║
║    GET  /status     — статус агента и LLM                    ║
║    GET  /check_llm  — проверка LLM                           ║
║    POST /run        — выполнить задачу                       ║
╚══════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
