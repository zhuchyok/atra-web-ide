"""
Victoria Agent Client (Улучшенная версия)
HTTP клиент для взаимодействия с Victoria (общий для всех проектов)
Retry logic, timeout handling, error recovery
"""
import httpx
import asyncio
import os
import uuid
from typing import AsyncGenerator, Optional
import logging
import json
from datetime import datetime

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VictoriaClient:
    """Клиент для Victoria Agent с улучшенной обработкой ошибок"""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.victoria_url
        self.timeout = httpx.Timeout(
            settings.victoria_timeout,
            connect=10.0
        )
        self.max_retries = 3
        self.retry_delay = 1.0
    
    async def _retry_request(self, func, *args, **kwargs):
        """Повторная попытка запроса с экспоненциальной задержкой"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
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
                response = await client.post(
                    f"{self.base_url}/plan",
                    json=payload
                )
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
        async def _make_request():
            logger.info("[VICTORIA_CYCLE] client POST /run goal_preview=%s timeout=%s max_steps=%s",
                        (prompt or "")[:80], self.timeout, max_steps)
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "goal": prompt,  # Victoria expects 'goal', not 'prompt'
                    "max_steps": max_steps,  # VICTORIA_MAX_STEPS_CHAT (50) — меньше «превышен лимит 500» на локальных моделях
                    "project_context": project_context or os.getenv("PROJECT_NAME", "atra-web-ide"),  # Контекст проекта
                }
                if session_id:
                    payload["session_id"] = session_id
                if chat_history:
                    payload["chat_history"] = chat_history[-30:]  # Последние 30 пар
                req_kw = {"json": payload}
                if correlation_id:
                    req_kw["headers"] = {"X-Correlation-ID": correlation_id}
                    logger.info("[VICTORIA_CYCLE] correlation_id=%s", correlation_id[:8])
                response = await client.post(f"{self.base_url}/run", **req_kw)
                response.raise_for_status()
                data = response.json()
                logger.info("[VICTORIA_CYCLE] client response status=%s output_len=%s",
                            data.get("status"), len(data.get("output") or data.get("result") or ""))
                return data
        
        try:
            data = await self._retry_request(_make_request)
            # Map Victoria response to expected format
            # Victoria может вернуть output в разных форматах
            output = data.get("output", "")
            if not output and "result" in data:
                output = data.get("result", "")
            if not output and "response" in data:
                output = data.get("response", "")
            
            logger.info(f"Victoria response: status={data.get('status')}, output_length={len(output) if output else 0}")
            
            return {
                "status": data.get("status", "success"),
                "result": output,
                "response": output,
                "raw": data,
                "clarification_questions": data.get("clarification_questions"),  # для needs_clarification
            }
        except httpx.HTTPError as e:
            logger.error("[VICTORIA_CYCLE] client error: %s", e)
            logger.error(f"Victoria error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "result": None
            }
    
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
        Стриминг ответа от Victoria (Singularity 14.0 Unified).
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
                async with client.stream("POST", f"{self.base_url}/stream", **stream_kw) as response:
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
            return {"status": "healthy", **result}
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
