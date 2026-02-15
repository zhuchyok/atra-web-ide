"""
Маршрутизатор запросов: делегирование Veronica по HTTP, fallback на Enhanced.
Используется в run_task при task_type == 'veronica' для прямого вызова Veronica Agent.
"""
import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger("victoria_bridge")

VERONICA_URL = (os.getenv("VERONICA_URL") or "http://localhost:8011").rstrip("/")
DELEGATE_VERONICA_TIMEOUT = int(os.getenv("DELEGATE_VERONICA_TIMEOUT", "90"))

# Лог при первом использовании (почему делегирование не срабатывает — часто неверный URL)
_logged_url = False


def _log_delegation_url_once():
    global _logged_url
    if not _logged_url:
        logger.info("[DELEGATION] VERONICA_URL=%s (из контейнера Victoria должен быть http://veronica-agent:8000)", VERONICA_URL)
        _logged_url = True


async def delegate_to_veronica(
    goal: str,
    project_context: str,
    correlation_id: Optional[str] = None,
    max_steps: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Делегирует задачу Veronica по HTTP (POST /run).
    Возвращает результат в формате TaskResponse (status, output, knowledge) или None при ошибке.
    """
    if not goal or not goal.strip():
        return None
    _log_delegation_url_once()
    url = f"{VERONICA_URL}/run"
    logger.info("[DELEGATION] VERONICA_URL=%s goal=%s correlation_id=%s timeout=%s", VERONICA_URL, (goal or "")[:50], (correlation_id or "")[:8], DELEGATE_VERONICA_TIMEOUT)
    payload: Dict[str, Any] = {
        "goal": goal,
        "project_context": project_context or os.getenv("MAIN_PROJECT", "atra-web-ide"),
    }
    if max_steps is not None:
        payload["max_steps"] = max_steps
    headers: Dict[str, str] = {}
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers or None,
                timeout=aiohttp.ClientTimeout(total=DELEGATE_VERONICA_TIMEOUT),
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    logger.warning(
                        "[DELEGATION] Veronica HTTP status=%s body=%s",
                        response.status, (body or "")[:300]
                    )
                    return None
                data = await response.json()
                if not isinstance(data, dict):
                    logger.warning("[DELEGATION] Veronica response not dict")
                    return None
                status = data.get("status")
                has_success = status == "success"
                logger.info("[DELEGATION] Veronica HTTP 200 status=%s has_success=%s", status, has_success)
                return {
                    "status": status or "success",
                    "output": data.get("output", ""),
                    "knowledge": data.get("knowledge") or {},
                    "correlation_id": correlation_id,
                }
    except Exception as e:
        err_msg = str(e)
        if "Timeout" in type(e).__name__ or "timeout" in err_msg.lower():
            logger.warning("[DELEGATION] Delegate timeout VERONICA_URL=%s timeout=%s", VERONICA_URL, DELEGATE_VERONICA_TIMEOUT)
        else:
            logger.warning(
                "[DELEGATION] error=%s — проверьте VERONICA_URL и что Veronica запущена",
                e
            )
        return None
