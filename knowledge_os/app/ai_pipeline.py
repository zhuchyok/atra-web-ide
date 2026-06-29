"""
Extracted pipeline phases from run_smart_agent_async_impl (ai_core.py).
Каждая фаза — отдельная функция для тестирования и поддержки.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─── Phase 1: Prompt Preparation ─────────────────────────────────────────

async def load_memory_crystals(project_context: Optional[str] = None) -> str:
    """Load memory crystals from DB."""
    try:
        from ai_core import _get_db_pool
        pool = await _get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT crystal_type, content FROM memory_crystals WHERE project_context = $1 ORDER BY created_at DESC LIMIT 10",
                    project_context or "atra-web-ide",
                )
                if rows:
                    text = "\n".join(f"[{r['crystal_type'].upper()}] {r['content']}" for r in rows)
                    logger.info(f"💎 [MEMORY CRYSTALS] Loaded {len(rows)} crystals")
                    return f"💎 ПАМЯТЬ ПРОЕКТА (MEMORY CRYSTALS):\n{text}\n"
    except Exception as e:
        logger.debug(f"Memory crystals load failed: {e}")
    return ""


def check_threats(prompt: str) -> Tuple[bool, List[str]]:
    """Check prompt for security threats."""
    try:
        from app.threat_detector import get_threat_detector
        td = get_threat_detector()
        results = td.analyze(prompt, "")
        if results:
            types = [t.get("threat_type", "unknown") for t in results]
            sev = max({"critical": 3, "high": 2, "medium": 1, "low": 0}.get(t.get("severity", "low"), 0) for t in results)
            return sev >= 3, types
    except Exception:
        pass
    return False, []


def inject_anti_hallucination(prompt: str, expert_name: str, is_discussion: bool = False) -> str:
    """Add anti-hallucination instructions for Victoria."""
    if not is_discussion and expert_name.lower() in ("виктория", "victoria"):
        instruction = """
### [CRITICAL: ANTI-HALLUCINATION]
Ты маленький помощник. Большая модель (Brain) планирует, ты только выполняешь.
ПРАВИЛА:
1. НИКОГДА не выдумывай факты, файлы, директории
2. Если не знаешь — отвечай 'Не знаю' или 'Нужно уточнить'
3. Не притворяйся, что помнишь разговор
4. Выполняй ТОЛЬКО то, что сказано в запросе
"""
        return instruction + "\n" + prompt
    return prompt


def inject_wisdom(prompt: str, is_discussion: bool = False) -> str:
    """Inject wisdom strategies."""
    if is_discussion:
        return prompt
    try:
        from ai_core import _inject_wisdom_strategies
        return _inject_wisdom_strategies(prompt)
    except Exception:
        return prompt


async def inject_expert_dna(prompt: str, expert_name: str) -> str:
    """Inject expert DNA rules."""
    try:
        from app.expert_dna_manager import get_expert_dna_manager
        dna_mgr = get_expert_dna_manager()
        dna = await dna_mgr.get_expert_dna(expert_name)
        if dna:
            return dna + "\n" + prompt
    except Exception:
        pass
    return prompt


# ─── Phase 2: Context & Strategy ─────────────────────────────────────────

async def get_cache_and_context(
    prompt: str, expert_name: str, category: Optional[str], project_context: Optional[str],
    images: Optional[list] = None
) -> Tuple[Optional[str], str]:
    """Check cache and load RAG context in parallel."""
    from ai_core import _get_knowledge_context, _get_cache_manager
    cache = _get_cache_manager(category)

    tasks = []
    if cache and not images:
        tasks.append(cache.get_cached_response(prompt, expert_name))
    else:
        tasks.append(asyncio.sleep(0, result=None))
    tasks.append(_get_knowledge_context(prompt, project_context))

    results = await asyncio.gather(*tasks)
    return results[0], results[1] or ""


# ─── Phase 3: Episodic & Distillation ─────────────────────────────────────

async def get_episodic_memory(user_key: str, project_context: Optional[str]) -> str:
    """Load episodic memory for user."""
    try:
        from ai_core import get_episodic_memory_manager
        em = get_episodic_memory_manager()
        if em:
            return await em.get_episodes(user_key, project_context) or ""
    except Exception:
        pass
    return ""


async def get_distilled_rules() -> str:
    """Load self-distillation rules."""
    try:
        from ai_core import get_distillation_engine
        de = get_distillation_engine()
        if de:
            return await de.get_active_rules() or ""
    except Exception:
        pass
    return ""


# ─── Phase 4: Cloud Execution ────────────────────────────────────────────

async def run_cloud(prompt: str, category: Optional[str] = None, is_vip: bool = False) -> Tuple[Optional[str], Optional[Dict]]:
    """Run LLM via cloud fallback."""
    try:
        from ai_core import _run_cloud_agent_async
        response = await _run_cloud_agent_async(prompt, category=category, is_vip=is_vip)
        return response, None
    except Exception as e:
        return None, {"error": str(e)}


# ─── Phase 5: Response Processing ────────────────────────────────────────

def clean_response(response: Any) -> str:
    """Normalize LLM response for user."""
    try:
        from ai_core import _normalize_output_for_user
        return _normalize_output_for_user(response)
    except Exception:
        return str(response) if response else ""


def strip_think_blocks(text: str) -> str:
    """Remove thinking blocks from response."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"</?think>", "", text)
    text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL)
    return text.strip()
