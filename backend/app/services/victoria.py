"""
Victoria Agent Client (Улучшенная версия)
HTTP клиент для взаимодействия с Victoria (общий для всех проектов)
Retry logic, timeout handling, error recovery
"""

import asyncio
import json
import logging
import os
import random
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VictoriaClient:
    """Клиент для Victoria Agent с улучшенной обработкой ошибок"""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.victoria_url
        self.timeout = httpx.Timeout(
            connect=10.0,
            read=float(settings.victoria_timeout),
            write=float(settings.victoria_timeout),
            pool=float(settings.victoria_timeout),
        )
        self.max_retries = 3
        # 5s base: даёт Victoria время отойти после перезапуска/прогрева (задержки 5s, 10s)
        self.retry_delay = 5.0

    async def _retry_request(self, func, *args, **kwargs):
        """Повторная попытка запроса с экспоненциальной задержкой"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except (httpx.HTTPError, httpx.TimeoutException, httpx.RequestError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.warning(
                        f"Victoria request failed (attempt {attempt + 1}/{self.max_retries}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Victoria request failed after {self.max_retries} attempts: {e}")

        raise last_error

    async def plan(self, goal: str, project_context: Optional[str] = None) -> dict:
        """
        Только план (режим Plan). Один вызов LLM, без выполнения инструментов.
        """

        async def _make_request():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {"goal": goal}
                if project_context:
                    payload["project_context"] = project_context
                response = await client.post(f"{self.base_url}/plan", json=payload)
                response.raise_for_status()
                return response.json()

        try:
            data = await self._retry_request(_make_request)
            plan = data.get("plan", "")
            return {"status": "success", "result": plan, "response": plan, "raw": data}
        except httpx.HTTPError as e:
            logger.error(f"Victoria plan error: {e}")
            return {"status": "error", "error": str(e), "result": None}

    async def run(
        self,
        prompt: str,
        expert_name: Optional[str] = None,
        stream: bool = False,
        project_context: Optional[str] = None,
        session_id: Optional[str] = None,
        chat_history: Optional[list] = None,
        correlation_id: Optional[str] = None,
        use_enhanced: Optional[bool] = None,
        max_poll_wait_sec: Optional[float] = None,
    ) -> dict:
        """
        Выполнить задачу через Victoria

        Args:
            prompt: Текст запроса (goal)
            expert_name: Имя эксперта (опционально)
            stream: Использовать стриминг
            project_context: Контекст проекта (atra-web-ide, atra, и т.д.)
            session_id: ID сессии для session_context (мировая практика: связный диалог)
            chat_history: История чата [{"user": "...", "assistant": "..."}] для Victoria
            correlation_id: ID для трассировки (чат → Victoria → Veronica). Передаётся в X-Correlation-ID.

        Returns:
            Результат выполнения
        """
        from app.config import get_settings

        settings = get_settings()
        max_steps = getattr(settings, "victoria_max_steps_chat", 50)
        # async_mode: не держим один sync-запрос 10+ минут — воркер Victoria не блокируется (VICTORIA_RESTARTS_CAUSE §4)
        poll_interval = 3.0
        poll_read_timeout = 30.0
        total_poll_timeout = float(getattr(settings, "victoria_timeout", 900))
        effective_poll_wait = total_poll_timeout
        if max_poll_wait_sec is not None:
            try:
                effective_poll_wait = max(5.0, min(total_poll_timeout, float(max_poll_wait_sec)))
            except Exception:
                effective_poll_wait = total_poll_timeout

        async def _make_request():
            logger.info(
                "[VICTORIA_CYCLE] client POST /run?async_mode=true goal_preview=%s timeout=%s max_steps=%s",
                (prompt or "")[:80],
                self.timeout,
                max_steps,
            )
            payload = {
                "goal": prompt,
                "max_steps": max_steps,
                "project_context": project_context or os.getenv("PROJECT_NAME", "atra-web-ide"),
            }
            if session_id:
                payload["session_id"] = session_id
            if chat_history:
                payload["chat_history"] = chat_history[-30:]
            if use_enhanced is not None:
                payload["use_enhanced"] = use_enhanced
            req_kw = {"json": payload}
            if correlation_id:
                req_kw["headers"] = {"X-Correlation-ID": correlation_id}
                logger.info("[VICTORIA_CYCLE] correlation_id=%s", correlation_id[:8])

            # Короткий таймаут на первый запрос: ждём подтверждение постановки в очередь (202) или быстрый sync (200).
            # Держим bounded submit, чтобы /api/chat/ask-victoria не зависал на раннем этапе.
            submit_timeout_sec = min(30.0, max(10.0, effective_poll_wait / 2.0))
            post_timeout = httpx.Timeout(
                connect=10.0,
                read=submit_timeout_sec,
                write=submit_timeout_sec,
                pool=submit_timeout_sec,
            )
            async with httpx.AsyncClient(timeout=post_timeout) as client:
                response = await client.post(f"{self.base_url}/run?async_mode=true", **req_kw)
                response.raise_for_status()
                data = response.json()

            if response.status_code == 200:
                # Sync-ответ (обратная совместимость)
                from app.utils.victoria_response_guard import reject_if_stub

                stub_reason = reject_if_stub(data)
                if stub_reason:
                    logger.warning(
                        "[VICTORIA_CYCLE] client sync rejected stub reason=%s", stub_reason
                    )
                    return {
                        "status": "error",
                        "error": f"Rejected stub response ({stub_reason})",
                        "output": "",
                        "result": None,
                    }
                logger.info("[VICTORIA_CYCLE] client sync response status=%s", data.get("status"))
                return data

            task_id = data.get("task_id")
            if not task_id:
                raise httpx.HTTPStatusError(
                    "No task_id in 202 response", request=response.request, response=response
                )
            logger.info(
                "[VICTORIA_CYCLE] client 202 task_id=%s polling /run/status/%s", task_id, task_id
            )

            status_url = f"{self.base_url}/run/status/{task_id}"
            poll_timeout = httpx.Timeout(
                connect=10.0,
                read=poll_read_timeout,
                write=poll_read_timeout,
                pool=poll_read_timeout,
            )
            deadline = asyncio.get_event_loop().time() + effective_poll_wait
            poll_connect_retries = 2
            poll_connect_retry_delay = 3.0
            async with httpx.AsyncClient(timeout=poll_timeout) as client:
                while True:
                    if asyncio.get_event_loop().time() >= deadline:
                        logger.info(
                            "[VICTORIA_CYCLE] client poll budget reached task_id=%s budget=%ss; returning processing",
                            task_id[:8],
                            effective_poll_wait,
                        )
                        return {
                            "status": "processing",
                            "task_id": task_id,
                            "status_url": status_url,
                            "message": f"Task is still running after {effective_poll_wait:.0f}s",
                        }
                    last_poll_err = None
                    for poll_attempt in range(poll_connect_retries):
                        try:
                            r = await client.get(status_url)
                            if r.status_code == 404:
                                return {
                                    "status": "error",
                                    "error": "Task lost (Victoria may have restarted). Please retry your request.",
                                    "output": "",
                                    "result": None,
                                }
                            r.raise_for_status()
                            st = r.json()
                            status_val = (st.get("status") or "").lower()
                            if status_val == "completed":
                                out = st.get("output") or st.get("result") or ""
                                from app.utils.victoria_response_guard import reject_if_stub

                                stub_reason = reject_if_stub(
                                    {"status": "completed", "output": out, "result": out}
                                )
                                if stub_reason:
                                    logger.warning(
                                        "[VICTORIA_CYCLE] client poll rejected stub task_id=%s reason=%s",
                                        task_id[:8],
                                        stub_reason,
                                    )
                                    return {
                                        "status": "error",
                                        "error": f"Rejected stub response ({stub_reason})",
                                        "output": "",
                                        "result": None,
                                    }
                                logger.info(
                                    "[VICTORIA_CYCLE] client poll completed output_len=%s", len(out)
                                )
                                return {
                                    "status": "success",
                                    "output": out,
                                    "result": out,
                                    "response": out,
                                }
                            if status_val == "failed":
                                err = st.get("error") or "Task failed"
                                logger.warning(
                                    "[VICTORIA_CYCLE] client poll failed error=%s", err[:200]
                                )
                                return {
                                    "status": "error",
                                    "error": err,
                                    "output": "",
                                    "result": None,
                                }
                            if status_val in ("queued", "processing"):
                                logger.debug(
                                    "[VICTORIA_CYCLE] client poll progress task_id=%s status=%s",
                                    task_id[:8],
                                    status_val,
                                )
                            break
                        except (
                            httpx.ConnectError,
                            httpx.TimeoutException,
                            httpx.RemoteProtocolError,
                        ) as e:
                            last_poll_err = e
                            if poll_attempt < poll_connect_retries - 1:
                                logger.warning(
                                    "[VICTORIA_CYCLE] poll GET %s (attempt %s/%s): %s, retry in %ss",
                                    task_id[:8],
                                    poll_attempt + 1,
                                    poll_connect_retries,
                                    e,
                                    poll_connect_retry_delay,
                                )
                                await asyncio.sleep(poll_connect_retry_delay)
                            else:
                                raise
                    # Adaptive polling: faster at start, then slower to reduce load.
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining > 45:
                        base_sleep = 2.0
                    elif remaining > 15:
                        base_sleep = 3.0
                    else:
                        base_sleep = 4.0
                    jitter = random.uniform(0.0, 0.6)
                    await asyncio.sleep(max(poll_interval, base_sleep) + jitter)

        try:
            data = await self._retry_request(_make_request)
            if (data.get("status") or "").lower() == "processing":
                return {
                    "status": "processing",
                    "error": None,
                    "result": data.get("message") or "",
                    "response": data.get("message") or "",
                    "raw": data,
                    "task_id": data.get("task_id"),
                    "status_url": data.get("status_url"),
                    "clarification_questions": data.get("clarification_questions"),
                }
            output = data.get("output", "")
            if not output and "result" in data:
                output = data.get("result", "")
            if not output and "response" in data:
                output = data.get("response", "")
            from app.utils.victoria_response_guard import reject_if_stub

            stub_reason = reject_if_stub(
                {
                    "status": data.get("status"),
                    "output": output,
                    "result": output,
                    "response": output,
                }
            )
            if stub_reason:
                logger.warning("[VICTORIA_CYCLE] client final rejected stub reason=%s", stub_reason)
                return {
                    "status": "error",
                    "error": f"Rejected stub response ({stub_reason})",
                    "result": None,
                    "response": None,
                    "raw": data,
                }
            logger.info(
                "Victoria response: status=%s, output_length=%s",
                data.get("status"),
                len(output) if output else 0,
            )
            return {
                "status": data.get("status", "success"),
                "error": data.get("error"),
                "result": output,
                "response": output,
                "raw": data,
                "clarification_questions": data.get("clarification_questions"),
            }
        except httpx.HTTPError as e:
            logger.error("[VICTORIA_CYCLE] client error: %s", e)
            return {"status": "error", "error": str(e), "result": None}

    async def run_stream(
        self,
        prompt: str,
        expert_name: Optional[str] = None,
        project_context: Optional[str] = None,
        session_id: Optional[str] = None,
        chat_history: Optional[list] = None,
        correlation_id: Optional[str] = None,
        mode: str = "agent",
    ) -> AsyncGenerator[str, None]:
        """
        Стриминг ответа от Victoria (Singularity 31.2+ Unified).
        Вызывает эндпоинт /stream на сервере Victoria.
        """
        from app.config import get_settings

        settings = get_settings()
        max_steps = getattr(settings, "victoria_max_steps_chat", 50)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "goal": prompt,
                "max_steps": max_steps,
                "project_context": project_context or os.getenv("PROJECT_NAME", "atra-web-ide"),
                "session_id": session_id,
                "mode": mode,
            }
            if expert_name:
                payload["expert_name"] = expert_name
            if chat_history:
                payload["chat_history"] = chat_history[-30:]

            stream_kw = {"json": payload}
            if correlation_id:
                stream_kw["headers"] = {"X-Correlation-ID": correlation_id}

            try:
                # Вызываем новый эндпоинт /stream
                async with client.stream(
                    "POST", f"{self.base_url}/stream", **stream_kw
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            yield line
            except httpx.HTTPError as e:
                logger.error("Victoria stream error: %s", e)
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
                yield f"data: {json.dumps({'type': 'end'})}\n\n"

    async def status(self) -> dict:
        """Получить статус Victoria"""

        async def _make_request():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/status")
                response.raise_for_status()
                return response.json()

        try:
            return await self._retry_request(_make_request)
        except httpx.HTTPError as e:
            logger.error(f"Victoria status error: {e}")
            return {"status": "offline", "error": str(e)}

    async def health(self) -> dict:
        """Health check Victoria"""

        async def _make_request():
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.base_url}/health")
                response.raise_for_status()
                return response.json()

        try:
            result = await self._retry_request(_make_request)
            # Принимаем как 'healthy', так и 'ok' (Victoria может вернуть разное)
            status = "healthy" if result.get("status") in ("healthy", "ok") else "unhealthy"
            return {"status": status, "victoria": result}
        except httpx.HTTPError as e:
            return {"status": "unhealthy", "error": str(e)}

    async def get_hidden_thoughts(self, session_id: str) -> dict:
        """Получить скрытые рассуждения для сессии (Summary Reader)"""

        async def _make_request():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/hidden-thoughts/{session_id}")
                response.raise_for_status()
                return response.json()

        try:
            return await self._retry_request(_make_request)
        except httpx.HTTPError as e:
            logger.error(f"Victoria hidden thoughts error: {e}")
            return {"status": "error", "error": str(e)}


# Singleton instance
victoria_client = VictoriaClient()


async def get_victoria_client() -> VictoriaClient:
    """Dependency для FastAPI"""
    return victoria_client
