"""
Title: Ask Victoria (Singularity 31.2+)
Author: ATRA
Description: REQUIRED — For every user request to DO or ANALYZE something you MUST call this tool in the same turn. Never answer "unavailable" or cite a previous source without calling first. Call only for action/analysis requests; for greetings or "who are you" answer yourself. Supports chat_history (from __messages__) and response_format (text|json).
Version: 1.1.0
"""

import asyncio
import json
import os
import random
from typing import Any, Dict, List, Literal, Optional

try:
    import httpx
except ImportError:
    httpx = None

from pydantic import BaseModel, Field

_BIBLE_CONTEXT_CACHE: Dict[str, str] = {}


def _load_text_excerpt(path: str, max_chars: int) -> str:
    if not path:
        return ""
    cached = _BIBLE_CONTEXT_CACHE.get(path)
    if cached is not None:
        return cached
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read(max_chars)
    except Exception:
        text = ""
    _BIBLE_CONTEXT_CACHE[path] = text
    return text


def _attach_bible_context(goal: str, project_context: str, bible_anchor: str) -> str:
    if not bible_anchor:
        return goal
    return (
        "КОРПОРАТИВНЫЙ КОНТЕКСТ ATRA (обязательный):\n"
        f"{bible_anchor}\n\n"
        f"project_context={project_context}\n"
        "Используй этот контекст как источник истины для терминов, роли системы и стандартов.\n\n"
        f"Задача пользователя:\n{goal}"
    )


def _rewrite_host_paths(goal: str, host_workspace: str, container_workspace: str) -> str:
    text = (goal or "").strip()
    if not text:
        return text
    host_root = (host_workspace or "").strip().rstrip("/")
    container_root = (container_workspace or "").strip().rstrip("/")
    if host_root and container_root and host_root in text:
        text = text.replace(host_root, container_root)
    return text


def _looks_like_filesystem_request(goal: str) -> bool:
    g = (goal or "").lower()
    fs_markers = (
        "/users/",
        "/app/",
        "/workspace/",
        "файл",
        "папк",
        "директори",
        "каталог",
        "list_directory",
        "read_file",
        "scan",
        "ls ",
        "tree ",
    )
    return any(marker in g for marker in fs_markers)


def _attach_filesystem_contract(goal: str, host_workspace: str, container_workspace: str) -> str:
    if not _looks_like_filesystem_request(goal):
        return goal
    return (
        "КОНТРАКТ ВЫПОЛНЕНИЯ (обязателен):\n"
        f"- Host workspace alias: {host_workspace} -> {container_workspace}\n"
        "- Для операций с файлами сначала используй инструменты list_directory/read_file, "
        "а не псевдокод.\n"
        "- Если доступ к пути не получен, верни явный статус ACCESS_ERROR и реальную ошибку.\n"
        "- Запрещено имитировать выполненный скан или запуск кода.\n\n"
        f"Задача пользователя:\n{goal}"
    )


def _messages_to_chat_history(
    messages: Optional[List[Dict[str, Any]]],
) -> Optional[List[Dict[str, str]]]:
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


def _is_victoria_stub(text: str) -> bool:
    """Reject queue/ack/rule-fallback stubs so the UI model does not treat them as answers."""
    t = (text or "").strip()
    if not t:
        return True
    low = t.lower()
    markers = (
        "queued to postgresql",
        "queued to postgres",
        "task queued",
        "status_url",
        "processing...",
        "все источники недоступны",
        "агенты временно недоступны",
        "rule-based статусный ответ",
        "rule-based research fallback",
        "[degraded_rule_fallback]",
        "ai временно недоступен",
        "fix not implemented",
    )
    return any(m in low for m in markers)


def _reject_stub_output(output: str) -> Optional[str]:
    """Return error message if stub; None if output looks real."""
    if _is_victoria_stub(output):
        return (
            "Rejected Victoria stub/queue/rule-fallback response. "
            "Call ask_victoria again; do not invent an answer from this stub."
        )
    return None


class Tools:
    class Valves(BaseModel):
        VICTORIA_URL: str = Field(
            default="http://victoria-agent:8000",
            description="Direct Victoria URL (full agent mode): http://victoria-agent:8000. Backend proxy remains available if USE_BACKEND_PROXY=true.",
        )
        USE_BACKEND_PROXY: bool = Field(
            default=True,
            description="If true, call backend /api/chat/ask-victoria. If false, call Victoria /run directly (fuller local agent behavior).",
        )
        ASK_VICTORIA_TIMEOUT: int = Field(
            default=1200, description="Timeout in seconds for Victoria response"
        )
        BACKEND_FALLBACK_URL: str = Field(
            default="http://atra-web-ide-backend:8000",
            description="Fallback backend URL for /api/chat/ask-victoria if direct Victoria call fails.",
        )
        HOST_WORKSPACE_PATH: str = Field(
            default="/Users/bikos/Documents/atra-web-ide",
            description="Host workspace path shown by users in Open WebUI.",
        )
        CONTAINER_WORKSPACE_PATH: str = Field(
            default="/workspace/atra-web-ide",
            description="Mounted workspace path visible from victoria-agent container.",
        )
        BACKEND_STATUS_POLL_INTERVAL_SEC: int = Field(
            default=3,
            description="Polling interval (seconds) for long backend tasks.",
        )
        BACKEND_STATUS_MAX_WAIT_SEC: int = Field(
            default=180,
            description="Maximum wait time (seconds) when backend reports processing.",
        )
        ALWAYS_ATTACH_BIBLE_CONTEXT: bool = Field(
            default=True,
            description="If true, attach compact MASTER_REFERENCE context to every ask_victoria call.",
        )
        BIBLE_CONTEXT_MAX_CHARS: int = Field(
            default=4000,
            description="Maximum number of characters to load from the Bible docs for per-request context.",
        )
        BIBLE_MASTER_PATH: str = Field(
            default="/workspace/global_docs/MASTER_REFERENCE.md",
            description="Primary Bible file path mounted into Open WebUI container.",
        )
        BIBLE_CHANGES_PATH: str = Field(
            default="/workspace/global_docs/CHANGES_FROM_OTHER_CHATS.md",
            description="Supplementary changes log path mounted into Open WebUI container.",
        )

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
        base = (
            (
                getattr(self.valves, "VICTORIA_URL", None)
                or os.getenv("VICTORIA_URL")
                or "http://victoria-agent:8000"
            )
            .strip()
            .rstrip("/")
        )
        timeout = getattr(self.valves, "ASK_VICTORIA_TIMEOUT", None) or int(
            os.getenv("ASK_VICTORIA_TIMEOUT", "600")
        )
        use_backend = getattr(self.valves, "USE_BACKEND_PROXY", False)
        host_workspace = (
            getattr(self.valves, "HOST_WORKSPACE_PATH", None)
            or os.getenv("ATRA_HOST_WORKSPACE")
            or "/Users/bikos/Documents/atra-web-ide"
        ).strip()
        container_workspace = (
            getattr(self.valves, "CONTAINER_WORKSPACE_PATH", None)
            or os.getenv("ATRA_CONTAINER_WORKSPACE")
            or "/workspace/atra-web-ide"
        ).strip()
        normalized_goal = _rewrite_host_paths(goal.strip(), host_workspace, container_workspace)
        goal_for_victoria = _attach_filesystem_contract(
            normalized_goal, host_workspace, container_workspace
        )
        if bool(getattr(self.valves, "ALWAYS_ATTACH_BIBLE_CONTEXT", True)):
            max_chars = int(
                getattr(self.valves, "BIBLE_CONTEXT_MAX_CHARS", None)
                or os.getenv("BIBLE_CONTEXT_MAX_CHARS")
                or 4000
            )
            master_path = (
                getattr(self.valves, "BIBLE_MASTER_PATH", None)
                or os.getenv("BIBLE_MASTER_PATH")
                or "/workspace/global_docs/MASTER_REFERENCE.md"
            )
            changes_path = (
                getattr(self.valves, "BIBLE_CHANGES_PATH", None)
                or os.getenv("BIBLE_CHANGES_PATH")
                or "/workspace/global_docs/CHANGES_FROM_OTHER_CHATS.md"
            )
            master_excerpt = _load_text_excerpt(master_path, max_chars)
            changes_excerpt = _load_text_excerpt(changes_path, max(1200, max_chars // 3))
            bible_anchor = ""
            if master_excerpt:
                bible_anchor += f"[MASTER_REFERENCE excerpt]\n{master_excerpt.strip()}\n"
            if changes_excerpt:
                bible_anchor += f"\n[CHANGES excerpt]\n{changes_excerpt.strip()}\n"
            if bible_anchor:
                goal_for_victoria = _attach_bible_context(
                    goal_for_victoria,
                    (project_context or "atra-web-ide").strip(),
                    bible_anchor.strip(),
                )
        payload: Dict[str, Any]
        backend_payload: Dict[str, Any]
        if use_backend:
            backend_base = (
                (
                    getattr(self.valves, "BACKEND_FALLBACK_URL", None)
                    or os.getenv("BACKEND_FALLBACK_URL")
                    or base
                )
                .strip()
                .rstrip("/")
            )
            url = f"{backend_base}/api/chat/ask-victoria"
            if response_format == "json":
                url = f"{url}?format=json"
            payload = {
                "goal": goal_for_victoria,
                "project_context": (project_context or "atra-web-ide").strip(),
            }
            backend_payload = dict(payload)
            if user_key and str(user_key).strip():
                payload["user_key"] = str(user_key).strip()
                backend_payload["user_key"] = str(user_key).strip()
            elif __user__ and isinstance(__user__.get("id"), str):
                payload["user_key"] = f"openwebui-{__user__['id']}"
                backend_payload["user_key"] = f"openwebui-{__user__['id']}"
            history = _messages_to_chat_history(__messages__)
            if history:
                payload["chat_history"] = history[-15:]
                backend_payload["chat_history"] = history[-15:]
        else:
            url = f"{base}/run"
            payload = {
                "goal": goal_for_victoria,
                "project_context": (project_context or "atra-web-ide").strip(),
                "use_enhanced": True,
                "workspace_path": container_workspace,
            }
            backend_payload = {
                "goal": goal_for_victoria,
                "project_context": (project_context or "atra-web-ide").strip(),
            }
            if user_key and str(user_key).strip():
                payload["session_id"] = str(user_key).strip()
                backend_payload["user_key"] = str(user_key).strip()
            elif __user__ and isinstance(__user__.get("id"), str):
                payload["session_id"] = f"openwebui-{__user__['id']}"
                backend_payload["user_key"] = f"openwebui-{__user__['id']}"
            history = _messages_to_chat_history(__messages__)
            if history:
                payload["chat_history"] = history[-15:]
                backend_payload["chat_history"] = history[-15:]
        data = None
        last_error = None
        retry_503_sec = 15  # пауза перед повтором при 503 (перегрузка)
        max_attempts = 3  # всего попыток: 1 обычная + до 2 повторов при 503/connection/timeout
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    r = await client.post(url, json=payload)
                    r.raise_for_status()
                    if use_backend:
                        ct = (r.headers.get("content-type") or "").lower()
                        if "application/json" in ct:
                            data = r.json()
                            if data.get("status") == "processing":
                                polled = await self._poll_backend_status(
                                    base_url=backend_base,
                                    task_id=str(data.get("task_id") or "").strip(),
                                    timeout=timeout,
                                    initial_poll_after_sec=int(data.get("poll_after_sec") or 3),
                                )
                                if polled is not None:
                                    return polled
                            output = data.get("result", "") or data.get("output", "")
                            if data.get("status") == "error" and not output:
                                return data.get(
                                    "error",
                                    "Victoria is temporarily unavailable for this attempt. On the user's next request, call ask_victoria again.",
                                )
                            out_s = output if isinstance(output, str) else str(output)
                            stub_err = _reject_stub_output(out_s)
                            if stub_err:
                                return stub_err
                            return out_s
                        return (
                            r.text
                            or "Victoria is temporarily unavailable for this attempt. On the user's next request, call ask_victoria again."
                        )
                    data = r.json()
                break
            except httpx.ConnectError:
                last_error = "Victoria is temporarily unavailable (connection error) for this attempt. On the user's next request, call ask_victoria again."
                if not use_backend:
                    fallback_result = await self._fallback_via_backend(
                        backend_payload=backend_payload,
                        timeout=timeout,
                        response_format=response_format,
                    )
                    if fallback_result is not None:
                        return fallback_result
                if attempt < max_attempts - 1:
                    await asyncio.sleep(3)
                    continue
                return last_error
            except httpx.TimeoutException:
                last_error = "Victoria took too long to respond. Ask the user to try again or simplify the request (e.g. one concrete task)."
                if not use_backend:
                    fallback_result = await self._fallback_via_backend(
                        backend_payload=backend_payload,
                        timeout=timeout,
                        response_format=response_format,
                    )
                    if fallback_result is not None:
                        return fallback_result
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
                if not use_backend:
                    fallback_result = await self._fallback_via_backend(
                        backend_payload=backend_payload,
                        timeout=timeout,
                        response_format=response_format,
                    )
                    if fallback_result is not None:
                        return fallback_result
                if attempt == 0:
                    await asyncio.sleep(5 if exc_name == "RemoteProtocolError" else 3)
                    continue
                return last_error
        if data is None:
            return (
                last_error
                or "Victoria is temporarily unavailable for this attempt. On the user's next request, call ask_victoria again."
            )
        status = data.get("status", "")
        output = data.get("output") or data.get("result") or ""
        if isinstance(output, dict):
            output = output.get("result", str(output))
        if not isinstance(output, str):
            output = str(output)
        if status != "success" and not output:
            return (
                data.get("error")
                or "Victoria is temporarily unavailable for this attempt. On the user's next request, call ask_victoria again."
            )
        stub_err = _reject_stub_output(output)
        if stub_err:
            return stub_err
        clarification = data.get("clarification_questions") or (data.get("knowledge") or {}).get(
            "clarification_questions"
        )
        if clarification:
            if isinstance(clarification, list):
                lines = [
                    f"Мне нужно уточнить: {q}" if isinstance(q, str) else str(q)
                    for q in clarification
                ]
                clarification_text = "\n".join(lines)
            else:
                clarification_text = str(clarification)
            return clarification_text + ("\n\n" + output if output else "")
        return output

    async def _fallback_via_backend(
        self,
        backend_payload: Dict[str, Any],
        timeout: int,
        response_format: Literal["text", "json"],
    ) -> Optional[str]:
        """
        Reliability fallback: when direct Victoria path is degraded, use backend /api/chat/ask-victoria.
        """
        base = (getattr(self.valves, "BACKEND_FALLBACK_URL", "") or "").strip().rstrip("/")
        if not base or httpx is None:
            return None
        url = f"{base}/api/chat/ask-victoria?format=json"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(url, json=backend_payload)
                r.raise_for_status()
                data = r.json()
                output = data.get("result", "") or data.get("output", "")
                if not output:
                    return None
                if response_format == "json":
                    return json.dumps({"status": "success", "result": output}, ensure_ascii=False)
                return output if isinstance(output, str) else str(output)
        except Exception:
            return None

    async def _poll_backend_status(
        self,
        base_url: str,
        task_id: str,
        timeout: int,
        initial_poll_after_sec: int = 3,
    ) -> Optional[str]:
        """Poll backend /ask-victoria/status for long-running tasks."""
        if not task_id:
            return None
        poll_interval = int(
            getattr(self.valves, "BACKEND_STATUS_POLL_INTERVAL_SEC", None)
            or os.getenv("BACKEND_STATUS_POLL_INTERVAL_SEC")
            or 3
        )
        max_wait = int(
            getattr(self.valves, "BACKEND_STATUS_MAX_WAIT_SEC", None)
            or os.getenv("BACKEND_STATUS_MAX_WAIT_SEC")
            or 180
        )
        status_url = f"{base_url.rstrip('/')}/api/chat/ask-victoria/status/{task_id}?format=json"
        deadline = asyncio.get_event_loop().time() + max_wait
        next_wait = max(1, initial_poll_after_sec)
        async with httpx.AsyncClient(timeout=timeout) as client:
            while asyncio.get_event_loop().time() < deadline:
                try:
                    r = await client.get(status_url)
                    r.raise_for_status()
                    data = r.json()
                    status = str(data.get("status") or "").lower()
                    output = data.get("result", "") or data.get("output", "")
                    if status == "success":
                        return output if isinstance(output, str) else str(output)
                    if status == "error":
                        if output:
                            return output if isinstance(output, str) else str(output)
                        return "Victoria returned an error while completing a long task."
                    advised = int(data.get("poll_after_sec") or next_wait)
                    next_wait = max(1, advised)
                except Exception:
                    # Keep polling until deadline; transient status errors should not fail fast.
                    pass
                # Exponential backoff with small jitter protects backend under load.
                jitter = random.uniform(0.0, 0.7)
                await asyncio.sleep(max(1, min(next_wait, poll_interval)) + jitter)
                next_wait = min(next_wait * 2, max(2, poll_interval))
        return (
            f"Victoria is still processing this task (task_id={task_id}). "
            "Please retry shortly to get the final result."
        )
