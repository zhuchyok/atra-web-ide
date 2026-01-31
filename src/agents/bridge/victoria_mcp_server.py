"""
Victoria MCP Server — подключение Victoria к Cursor через MCP.
Запуск: python -m src.agents.bridge.victoria_mcp_server
"""
import asyncio
import os
import httpx
import logging
from mcp.server.fastmcp import FastMCP
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("victoria_mcp")

# Victoria на Mac Studio (192.168.1.64). Переопределение: VICTORIA_URL.
VICTORIA_URL = os.getenv(
    "VICTORIA_URL",
    "http://192.168.1.64:8010",  # Mac Studio — основной сервер Victoria
)

mcp = FastMCP(
    "VictoriaATRA",
    host="0.0.0.0",
    port=8012,
    sse_path="/sse"
)


def _parse_run_result(result: dict) -> str:
    """Разбор ответа /run: поддержка goal→output и prompt→response."""
    out = result.get("output") or result.get("response") or result.get("result")
    if out is None:
        return "(Victoria приняла запрос; ответ пуст)"
    status = result.get("status", "completed")
    return f"✅ {status}\n\n{out}"


@mcp.tool()
async def victoria_run(goal: str, max_steps: Optional[int] = 500) -> str:
    """Запустить задачу через Victoria Agent (Team Lead ATRA).
    
    Args:
        goal: Цель/задача для выполнения
        max_steps: Максимальное количество шагов (по умолчанию 500)
    
    Returns:
        Результат выполнения задачи от Victoria
    """
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            # 1) Стандартный API (goal + max_steps)
            resp = await client.post(
                f"{VICTORIA_URL}/run",
                json={"goal": goal, "max_steps": max_steps}
            )
            # 2) При 422 пробуем API с prompt (Mac Studio / иные деплои)
            if resp.status_code == 422:
                resp = await client.post(
                    f"{VICTORIA_URL}/run",
                    json={"prompt": goal}
                )
            resp.raise_for_status()
            data = resp.json()
            return _parse_run_result(data)
    except httpx.TimeoutException:
        return "⏱️ Таймаут: задача заняла слишком много времени."
    except httpx.RequestError as e:
        return f"❌ Ошибка связи с Victoria: {e}"
    except Exception as e:
        logger.exception("Ошибка victoria_run")
        return f"❌ Ошибка: {e}"


@mcp.tool()
async def victoria_status() -> str:
    """Проверить статус Victoria Agent.
    
    Returns:
        Статус Victoria (online/offline, knowledge size)
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{VICTORIA_URL}/status")
            if response.status_code == 404:
                health = await client.get(f"{VICTORIA_URL}/health")
                if health.is_success:
                    return "✅ Victoria на связи (Mac Studio). Эндпоинт /status не реализован — используй victoria_health."
                health.raise_for_status()
            response.raise_for_status()
            data = response.json()
            return f"✅ Victoria: {data.get('status', 'unknown')}\nЗнаний: {data.get('knowledge_size', 0)}"
    except Exception as e:
        return f"❌ Victoria недоступна: {e}"


@mcp.tool()
async def victoria_health() -> str:
    """Проверить здоровье Victoria Agent.
    
    Returns:
        Health check результат
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{VICTORIA_URL}/health")
            response.raise_for_status()
            data = response.json()
            return f"✅ {data.get('status', 'ok')} — {data.get('agent', 'Victoria')}"
    except Exception as e:
        return f"❌ Victoria не отвечает: {e}"


if __name__ == "__main__":
    logger.info(f"🚀 Victoria MCP Server запущен на http://0.0.0.0:8012")
    logger.info(f"   SSE: http://localhost:8012/sse")
    logger.info(f"   Victoria API: {VICTORIA_URL}")
    
    # Запуск в режиме SSE для Cursor
    mcp.run(transport="sse")
