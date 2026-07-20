"""
Local LLM calls for expert-dialogue engines (hybrid quality-local).

Policy:
- Wait for local Ollama/MLX (no cloud by default).
- Retry Ollama 503 busy within budget.
- Never invent a fake expert opinion — return incomplete + reason instead.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_THINK_BLOCK_RE = re.compile(
    r"<think>.*?</think>|<thinking>.*?</thinking>",
    flags=re.IGNORECASE | re.DOTALL,
)


def _strip_model_artifacts(text: str) -> str:
    """Remove model thinking tags / leading junk that confuse board gates."""
    cleaned = _THINK_BLOCK_RE.sub("", text or "")
    cleaned = cleaned.strip().lstrip(".\n").strip()
    return cleaned


MLX_BASE = os.getenv("MLX_BASE_URL", "http://host.docker.internal:11435").rstrip("/")
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434").rstrip("/")
DEFAULT_OLLAMA_MODEL = os.getenv("DIALOGUE_OLLAMA_MODEL", "phi3.5:3.8b")
DEFAULT_MLX_MODEL = os.getenv("DIALOGUE_MLX_MODEL", "victoria-wisdom-v3.5")
HTTP_TIMEOUT = float(os.getenv("DIALOGUE_LLM_TIMEOUT_SEC", "90"))
MLX_TIMEOUT = float(os.getenv("DIALOGUE_MLX_TIMEOUT_SEC", "60"))
MAX_TOKENS = max(64, int(os.getenv("DIALOGUE_MAX_TOKENS", "280")))
OLLAMA_MAX_CANDIDATES = max(1, int(os.getenv("DIALOGUE_OLLAMA_MAX_CANDIDATES", "2")))
PREFER_OLLAMA_FIRST = os.getenv("DIALOGUE_PREFER_OLLAMA_FIRST", "true").lower() in (
    "1",
    "true",
    "yes",
)
_FALLBACK_MODELS = [
    "phi3.5:3.8b",
    "phi3.5:3.8b-stable",
    "smollm2:360m",
    "tinyllama:1.1b-chat",
    "victoria-wisdom-v3.5:latest",
]

INCOMPLETE_MARKER = "[INCOMPLETE]"


@dataclass
class DialogueGenResult:
    text: str
    ok: bool
    reason: str = ""  # ok | ollama_busy | timeout | unavailable | empty

    @property
    def incomplete(self) -> bool:
        return not self.ok


def is_incomplete_text(text: str) -> bool:
    t = (text or "").lower()
    return (
        INCOMPLETE_MARKER.lower() in t
        or "local model did not finish" in t
        or "local model incomplete" in t
        or "временно недоступен" in t
        or "opinion unavailable" in t
        or "synthesis incomplete" in t
    )


async def generate_dialogue(
    prompt: str,
    *,
    expert_name: str = "expert",
    model_hint: Optional[str] = None,
    backends: tuple[str, ...] | None = None,
) -> DialogueGenResult:
    """Generate text via local inference; honest incomplete on failure.

    backends: optional explicit order, e.g. ("mlx",) for Victoria-first board path
    so a slow MLX miss does not burn the outer timeout on Ollama.
    """
    last_reason = "unavailable"
    if backends:
        order = backends
    else:
        order = ("ollama", "mlx") if PREFER_OLLAMA_FIRST else ("mlx", "ollama")
    for backend in order:
        if backend == "ollama":
            text, reason = await _try_ollama(prompt, model_hint=model_hint)
        elif backend == "mlx":
            text, reason = await _try_mlx(prompt, model_hint=model_hint)
        else:
            continue
        if text:
            cleaned = _strip_model_artifacts(text)
            if cleaned:
                return DialogueGenResult(text=cleaned, ok=True, reason="ok")
        if reason:
            last_reason = reason
    logger.warning("dialogue_llm: incomplete for %s reason=%s", expert_name, last_reason)
    return DialogueGenResult(
        text=(
            f"{INCOMPLETE_MARKER} [{expert_name}] local model incomplete "
            f"(reason={last_reason}). No fabricated opinion."
        ),
        ok=False,
        reason=last_reason,
    )


async def generate_dialogue_text(
    prompt: str,
    *,
    expert_name: str = "expert",
    model_hint: Optional[str] = None,
) -> str:
    """Backward-compatible wrapper."""
    result = await generate_dialogue(prompt, expert_name=expert_name, model_hint=model_hint)
    return result.text


async def _resolve_ollama_model(model_hint: Optional[str]) -> str:
    hint = (model_hint or "").strip()
    if hint in ("", "fast", "reasoning", "default"):
        hint = DEFAULT_OLLAMA_MODEL
    available: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            if resp.status_code == 200:
                available = [m.get("name", "") for m in resp.json().get("models", [])]
    except Exception as e:
        logger.debug("dialogue_llm tags failed: %s", e)
    if hint in available:
        return hint
    base = hint.split(":")[0]
    for name in available:
        if name == hint or name.startswith(base + ":"):
            return name
    for cand in _FALLBACK_MODELS:
        if cand in available:
            return cand
        for name in available:
            if name.startswith(cand.split(":")[0] + ":") or name == cand:
                return name
    return available[0] if available else DEFAULT_OLLAMA_MODEL


async def _try_mlx(prompt: str, *, model_hint: Optional[str]) -> tuple[str, str]:
    model = DEFAULT_MLX_MODEL
    if (
        model_hint
        and ":" not in str(model_hint)
        and model_hint
        not in (
            "fast",
            "reasoning",
            "default",
        )
    ):
        model = model_hint
    # Local MLX server speaks Ollama-compatible /api/chat (not OpenAI /v1/chat/completions).
    url = f"{MLX_BASE}/api/chat"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"num_predict": MAX_TOKENS, "temperature": 0.4},
    }
    try:
        async with httpx.AsyncClient(timeout=MLX_TIMEOUT) as client:
            resp = await client.post(url, json=body)
            if resp.status_code == 503:
                return "", "mlx_busy"
            if resp.status_code != 200:
                logger.warning(
                    "dialogue_llm MLX status %s model=%s body=%s",
                    resp.status_code,
                    model,
                    (resp.text or "")[:160],
                )
                return "", "unavailable"
            data = resp.json()
            msg = data.get("message") or {}
            content = msg.get("content") if isinstance(msg, dict) else None
            if content:
                return str(content), "ok"
            if data.get("response"):
                return str(data["response"]), "ok"
            choices = data.get("choices") or []
            if choices:
                cmsg = choices[0].get("message") or {}
                ccontent = cmsg.get("content") or choices[0].get("text")
                if ccontent:
                    return str(ccontent), "ok"
    except httpx.TimeoutException:
        return "", "timeout"
    except Exception as e:
        logger.debug("dialogue_llm MLX miss: %s", e)
    return "", "unavailable"


async def _try_ollama(prompt: str, *, model_hint: Optional[str]) -> tuple[str, str]:
    primary = await _resolve_ollama_model(model_hint)
    candidates = [primary]
    for cand in _FALLBACK_MODELS:
        if cand not in candidates:
            candidates.append(cand)
    url = f"{OLLAMA_BASE}/api/generate"
    max_retries = max(1, int(os.getenv("DIALOGUE_OLLAMA_BUSY_RETRIES", "6")))
    busy_sleep = float(os.getenv("DIALOGUE_OLLAMA_BUSY_SLEEP_SEC", "8"))
    deadline = time.monotonic() + HTTP_TIMEOUT
    saw_busy = False
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        for model in candidates[:OLLAMA_MAX_CANDIDATES]:
            body = {
                "model": model,
                "prompt": prompt[:4000],
                "stream": False,
                "options": {"num_predict": MAX_TOKENS, "temperature": 0.4},
            }
            for attempt in range(1, max_retries + 1):
                remaining = deadline - time.monotonic()
                if remaining <= 0.5:
                    return "", "timeout" if not saw_busy else "ollama_busy"
                try:
                    resp = await client.post(url, json=body)
                    if resp.status_code == 503 or "server busy" in (resp.text or "").lower():
                        saw_busy = True
                        logger.warning(
                            "dialogue_llm Ollama busy model=%s attempt=%s/%s",
                            model,
                            attempt,
                            max_retries,
                        )
                        await asyncio.sleep(min(busy_sleep, max(0.5, deadline - time.monotonic())))
                        continue
                    if resp.status_code != 200:
                        logger.warning(
                            "dialogue_llm Ollama status %s model=%s body=%s",
                            resp.status_code,
                            model,
                            resp.text[:160],
                        )
                        break
                    data = resp.json()
                    text = str(data.get("response") or "").strip()
                    if text:
                        return text, "ok"
                    break
                except httpx.TimeoutException:
                    return "", "timeout"
                except Exception as e:
                    logger.warning(
                        "dialogue_llm Ollama failed model=%s attempt=%s: %s",
                        model,
                        attempt,
                        e,
                    )
                    await asyncio.sleep(min(busy_sleep, max(0.5, deadline - time.monotonic())))
    if saw_busy:
        return "", "ollama_busy"
    return "", "unavailable"
