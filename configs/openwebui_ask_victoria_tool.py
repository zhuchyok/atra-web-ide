"""
Title: Ask Victoria (Singularity 15.0)
Author: ATRA
Description: REQUIRED — For every user request to DO or ANALYZE something you MUST call this tool in the same turn. Never answer "unavailable" or cite a previous source without calling first. Call only for action/analysis requests; for greetings or "who are you" answer yourself. Supports chat_history (from __messages__) and response_format (text|json).
Version: 1.1.0
"""
import asyncio
import json
import os
from typing import Optional, List, Dict, Any, Literal

try:
    import httpx
except ImportError:
    httpx = None

from pydantic import BaseModel, Field


def _messages_to_chat_history(messages: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, str]]]:
    """Convert Open WebUI __messages__ (role/content) to Victoria format [{user, assistant}, ...]."""
    if not messages or not isinstance(messages, list):
        return None
    pairs = []
    user_content = None
    for msg in messages[-20:]:
        if not isinstance(msg, dict):
            continue
        role = (msg.get("role") or "").lower()
        content = (msg.get("content") or "")[:2000]
        if role == "user":
            user_content = content
        elif role == "assistant" and user_content is not None:
            pairs.append({"user": user_content, "assistant": content})
            user_content = None
    return pairs if pairs else None


class Tools:
    class Valves(BaseModel):
        VICTORIA_URL: str = Field(
            default="http://atra-web-ide-backend:8000",
            description="Backend URL (same as Cursor): http://atra-web-ide-backend:8000. Or direct Victoria: http://victoria-agent:8000 if USE_BACKEND_PROXY=false.",
        )
        USE_BACKEND_PROXY: bool = Field(
            default=True,
            description="If true, call backend /api/chat/ask-victoria (3 retries, 900s timeout, same as Cursor). Recommended.",
        )
        ASK_VICTORIA_TIMEOUT: int = Field(default=600, description="Timeout in seconds for Victoria response")

    def __init__(self):
        self.valves = self.Valves()

    async def ask_victoria(
        self,
        goal: str,
        project_context: str = "atra-web-ide",
        user_key: Optional[str] = None,
        response_format: Literal["text", "json"] = "text",
        __user__: Optional[dict] = None,
        __messages__: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        REQUIRED: For EVERY user message that asks to DO or ANALYZE something (e.g. "проанализируй проект X", "сделай Y"), you MUST call this tool in THIS turn. Do NOT answer "Victoria unavailable" or cite a previous source/conversation without calling ask_victoria first — always call, then if the call fails report that.
        Call when the user asked to DO something (write/fix code, check, create file, analyze). Do NOT call for greetings, "who are you", or general chat.
        :param goal: The concrete task for Victoria (required). E.g. "Analyze project setki-21" or "Add function to utils.py".
        :param project_context: Project: atra-web-ide, setki-21, or atra. Default atra-web-ide.
        :param user_key: Stable user id for memory, e.g. openwebui-{user_id}.
        :param response_format: "text" (default) or "json" — backend returns JSON with status/result when json.
        :param __user__: User context (filled by Open WebUI).
        :param __messages__: Recent messages (filled by Open WebUI); converted to chat_history for Victoria.
        """
        if not (goal or "").strip():
            return "Error: goal is required and cannot be empty."
        if httpx is None:
            return "Victoria is temporarily unavailable; try again later. (httpx not installed)"
        base = (getattr(self.valves, "VICTORIA_URL", None) or os.getenv("VICTORIA_URL") or "http://victoria-agent:8000").strip().rstrip("/")
        timeout = getattr(self.valves, "ASK_VICTORIA_TIMEOUT", None) or int(os.getenv("ASK_VICTORIA_TIMEOUT", "600"))
        use_backend = getattr(self.valves, "USE_BACKEND_PROXY", False)
        payload: Dict[str, Any]
        if use_backend:
            url = f"{base}/api/chat/ask-victoria"
            if response_format == "json":
                url = f"{url}?format=json"
            payload = {
                "goal": goal.strip(),
                "project_context": (project_context or "atra-web-ide").strip(),
            }
            if user_key and str(user_key).strip():
                payload["user_key"] = str(user_key).strip()
            elif __user__ and isinstance(__user__.get("id"), str):
                payload["user_key"] = f"openwebui-{__user__['id']}"
            history = _messages_to_chat_history(__messages__)
            if history:
                payload["chat_history"] = history[-15:]
        else:
            url = f"{base}/run"
            payload = {
                "goal": goal.strip(),
                "project_context": (project_context or "atra-web-ide").strip(),
                "use_enhanced": True,
            }
            if user_key and str(user_key).strip():
                payload["session_id"] = str(user_key).strip()
            elif __user__ and isinstance(__user__.get("id"), str):
                payload["session_id"] = f"openwebui-{__user__['id']}"
            history = _messages_to_chat_history(__messages__)
            if history:
                payload["chat_history"] = history[-15:]
        data = None
        last_error = None
        retry_503_sec = 15  # пауза перед повтором при 503 (перегрузка)
        max_attempts = 3     # всего попыток: 1 обычная + до 2 повторов при 503/connection/timeout
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    r = await client.post(url, json=payload)
                    r.raise_for_status()
                    if use_backend:
                        ct = (r.headers.get("content-type") or "").lower()
                        if "application/json" in ct:
                            data = r.json()
                            output = data.get("result", "") or data.get("output", "")
                            if data.get("status") == "error" and not output:
                                return data.get("error", "Victoria is temporarily unavailable for this attempt. On the user's next request, call ask_victoria again.")
                            return output if isinstance(output, str) else str(output)
                        return r.text or "Victoria is temporarily unavailable for this attempt. On the user's next request, call ask_victoria again."
                    data = r.json()
                break
            except httpx.ConnectError:
                last_error = "Victoria is temporarily unavailable (connection error) for this attempt. On the user's next request, call ask_victoria again."
                if attempt < max_attempts - 1:
                    await asyncio.sleep(3)
                    continue
                return last_error
            except httpx.TimeoutException:
                last_error = "Victoria took too long to respond. Ask the user to try again or simplify the request (e.g. one concrete task)."
                if attempt < max_attempts - 1:
                    await asyncio.sleep(3)
                    continue
                return last_error
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 503:
                    last_error = "Victoria is temporarily unavailable (server busy) for this attempt. On the user's next request, call ask_victoria again — do not skip the call based on this message."
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(retry_503_sec)
                        continue
                    return last_error
                return f"Victoria returned an error (HTTP {e.response.status_code}). Ask the user to try again later."
            except Exception as e:
                exc_name = type(e).__name__
                if exc_name == "RemoteProtocolError":
                    last_error = "Victoria closed the connection before answering (often on long tasks). Ask the user to try again or use a shorter request."
                else:
                    last_error = f"Victoria is temporarily unavailable ({exc_name}) for this attempt. On the user's next request, call ask_victoria again."
                if attempt == 0:
                    await asyncio.sleep(5 if exc_name == "RemoteProtocolError" else 3)
                    continue
                return last_error
        if data is None:
            return last_error or "Victoria is temporarily unavailable for this attempt. On the user's next request, call ask_victoria again."
        status = data.get("status", "")
        output = data.get("output") or data.get("result") or ""
        if isinstance(output, dict):
            output = output.get("result", str(output))
        if not isinstance(output, str):
            output = str(output)
        if status != "success" and not output:
            return data.get("error") or "Victoria is temporarily unavailable for this attempt. On the user's next request, call ask_victoria again."
        clarification = data.get("clarification_questions") or (data.get("knowledge") or {}).get("clarification_questions")
        if clarification:
            if isinstance(clarification, list):
                lines = [f"Мне нужно уточнить: {q}" if isinstance(q, str) else str(q) for q in clarification]
                clarification_text = "\n".join(lines)
            else:
                clarification_text = str(clarification)
            return clarification_text + ("\n\n" + output if output else "")
        return output
