"""
Victoria MCP Server — подключение Victoria к Cursor через MCP.
Запуск: python -m src.agents.bridge.victoria_mcp_server
"""

import json
import logging
import os
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("victoria_mcp")

# Victoria: localhost для работы с Cursor на этой машине; Mac Studio — через VICTORIA_URL.
VICTORIA_URL = os.getenv(
    "VICTORIA_URL",
    "http://localhost:8010",
)
# Таймаут для victoria_run (сек). Задачи на код (оркестратор → эксперты) часто > 5 мин. По умолчанию 10 мин.
VICTORIA_MCP_RUN_TIMEOUT_SEC = float(os.getenv("VICTORIA_MCP_RUN_TIMEOUT_SEC", "600"))

mcp = FastMCP("VictoriaATRA", host="0.0.0.0", port=8012, sse_path="/sse")


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
        timeout_sec = VICTORIA_MCP_RUN_TIMEOUT_SEC
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            # 1) Стандартный API (goal + max_steps)
            resp = await client.post(
                f"{VICTORIA_URL}/run", json={"goal": goal, "max_steps": max_steps}
            )
            # 2) При 422 пробуем API с prompt (Mac Studio / иные деплои)
            if resp.status_code == 422:
                resp = await client.post(f"{VICTORIA_URL}/run", json={"prompt": goal})
            resp.raise_for_status()
            data = resp.json()
            return _parse_run_result(data)
    except httpx.TimeoutException:
        return f"⏱️ Таймаут: задача заняла больше {int(VICTORIA_MCP_RUN_TIMEOUT_SEC)} с. Увеличьте VICTORIA_MCP_RUN_TIMEOUT_SEC или упростите задачу."
    except httpx.RequestError as e:
        return f"❌ Ошибка связи с Victoria: {e}"
    except Exception as e:
        logger.exception("Ошибка victoria_run")
        return f"❌ Ошибка: {e}"


@mcp.tool()
async def victoria_chat(
    message: str,
    history_json: Optional[str] = None,
    project_context: Optional[str] = "atra-web-ide",
) -> str:
    """Написать сообщение Виктории и получить ответ (для диалога).

    Args:
        message: Сообщение/вопрос для Виктории
        history_json: Опционально — JSON история диалога [{"user":"...","assistant":"..."}]
        project_context: Контекст проекта (по умолчанию atra-web-ide)

    Returns:
        Ответ Виктории
    """
    try:
        payload: dict = {
            "goal": message,
            "project_context": project_context,
        }
        if history_json:
            try:
                history = json.loads(history_json)
                if isinstance(history, list):
                    payload["chat_history"] = history
            except json.JSONDecodeError:
                pass
        async with httpx.AsyncClient(timeout=VICTORIA_MCP_RUN_TIMEOUT_SEC) as client:
            resp = await client.post(
                f"{VICTORIA_URL}/run",
                json=payload,
            )
            if resp.status_code == 422:
                resp = await client.post(
                    f"{VICTORIA_URL}/run",
                    json={"prompt": message},
                )
            resp.raise_for_status()
            data = resp.json()
            return _parse_run_result(data)
    except httpx.TimeoutException:
        return f"⏱️ Таймаут: Victoria не ответила за {int(VICTORIA_MCP_RUN_TIMEOUT_SEC)} с. Упрости запрос или увеличь VICTORIA_MCP_RUN_TIMEOUT_SEC."
    except httpx.RequestError as e:
        return f"❌ Ошибка связи с Victoria: {e}"
    except Exception as e:
        logger.exception("Ошибка victoria_chat")
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
    logger.info("🚀 Victoria MCP Server запущен на http://0.0.0.0:8012")
    logger.info("   SSE: http://localhost:8012/sse")
    logger.info(f"   Victoria API: {VICTORIA_URL}")

    # Запуск в режиме SSE для Cursor
    mcp.run(transport="sse")
