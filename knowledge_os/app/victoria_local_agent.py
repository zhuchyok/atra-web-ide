"""
Local-first agent runner for Docker/corp loops.

Cursor CLI (`cursor-agent` binary) is NOT required and must not be invoked.
Prefer Victoria smart core → LocalAIRouter (MLX/Ollama).
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def generate_local(
    prompt: str,
    *,
    category: str = "reasoning",
    expert_name: str = "Виктория",
    prefer_router: bool = False,
    model_hint: str | None = None,
) -> str | None:
    """Generate text via local stack only. Returns None on total failure."""
    text = (prompt or "").strip()
    if not text:
        return None

    async def _via_router() -> str | None:
        from local_router import LocalAIRouter

        router = LocalAIRouter()
        kwargs = {"category": category, "expert_name": expert_name}
        if model_hint:
            kwargs["model_hint"] = model_hint
        result = await router.run_local_llm(text, **kwargs)
        out = result[0] if isinstance(result, tuple) else result
        if out and len(str(out).strip()) > 10:
            return str(out).strip()
        return None

    async def _via_ai_core() -> str | None:
        from ai_core import run_smart_agent_async

        out = await run_smart_agent_async(text, expert_name=expert_name, category=category)
        if out and len(str(out).strip()) > 10:
            return str(out).strip()
        return None

    # Evolver/mutation loops: prefer direct Ollama/MLX (avoid heavy orchestration hangs).
    order = (_via_router, _via_ai_core) if prefer_router else (_via_ai_core, _via_router)
    for step in order:
        try:
            out = await step()
            if out:
                return out
        except Exception as exc:
            logger.debug("victoria_local_agent %s failed: %s", step.__name__, exc)

    logger.warning("victoria_local_agent: all local backends failed")
    return None


def generate_local_sync(
    prompt: str,
    *,
    category: str = "reasoning",
    expert_name: str = "Виктория",
) -> str | None:
    """Sync wrapper for legacy callers (safe outside running event loop)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # Nested call from async context — schedule a bridge thread.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                lambda: asyncio.run(
                    generate_local(prompt, category=category, expert_name=expert_name)
                )
            ).result(timeout=420)
    return asyncio.run(generate_local(prompt, category=category, expert_name=expert_name))
