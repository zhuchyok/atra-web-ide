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


async def inject_context_enrichment(
    expert_name: str, user_part: str, project_context: Optional[str] = None
) -> Dict[str, str]:
    """Load wisdom, mentorship, experience, success, and DNA context from DB."""
    result = {
        "meta_wisdom": "",
        "mentorship": "",
        "experience": "",
        "constitution": "",
    }
    try:
        from digital_constitution import get_constitution_context
        result["constitution"] = get_constitution_context()

        from ai_core import _get_db_pool
        pool = await _get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                # Meta-Strategies
                rows = await conn.fetch(
                    "SELECT content FROM knowledge_nodes WHERE metadata->>'type' = 'meta_wisdom' AND is_verified = TRUE ORDER BY created_at DESC LIMIT 3"
                )
                if rows:
                    texts = "\n".join(f"- {r['content']}" for r in rows)
                    result["meta_wisdom"] = f"\n### 🏛 CORPORATE META-STRATEGIES (WISDOM):\n{texts}\n"
                    logger.info(f"🏛 [WISDOM] Injected {len(rows)} meta-strategies")

                # Mentorship
                rows = await conn.fetch(
                    "SELECT content FROM knowledge_nodes WHERE metadata->>'type' = 'mentorship_note' AND metadata->>'target_expert' = $1 ORDER BY created_at DESC LIMIT 2",
                    expert_name,
                )
                if rows:
                    texts = "\n".join(f"- {r['content']}" for r in rows)
                    result["mentorship"] = f"\n### 🎓 MENTORSHIP FOR {expert_name}:\n{texts}\n"

        # Experience & Success
        try:
            from experience_retriever import get_experience_context
            exp = await get_experience_context(user_part, expert_name)
            if exp:
                result["experience"] = exp
        except Exception:
            pass
        try:
            from success_retriever import get_success_context
            suc = await get_success_context(user_part, expert_name=expert_name)
            if suc:
                result["experience"] += suc
        except Exception:
            pass

        # Expert DNA
        try:
            from expert_dna_manager import get_expert_dna_manager
            dna = await get_expert_dna_manager().get_expert_dna(expert_name)
            if dna:
                result["experience"] = dna + "\n" + result["experience"]
                logger.info(f"🧬 [EXPERT DNA] Injected for {expert_name}")
        except Exception:
            pass
    except Exception as e:
        logger.debug(f"Context enrichment failed: {e}")
    return result


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


# ─── V2 Pipeline: run_smart_agent_async clean implementation ──────────────

import os as _os
from datetime import datetime as _datetime
from typing import Optional as _Optional

async def run_smart_agent_async_v2(
    prompt: str,
    expert_name: str = "Виктория",
    category: _Optional[str] = None,
    require_cot: bool = False,
    is_critical: bool = False,
    images: _Optional[list] = None,
    session_id: _Optional[str] = None,
    local_router=None,
    is_vip: bool = False,
    project_context: _Optional[str] = None,
) -> str:
    """
    [SINGULARITY 31.3] Clean pipeline for LLM calls.
    Uses extracted phases from ai_pipeline. Falls back to original if error.
    """
    import time
    start = time.time()

    try:
        from ai_core import (
            _get_db_pool, _get_local_router, _get_cache_manager,
            audit_efficiency, _build_error_response, _get_expert_id,
            _normalize_output_for_user, _run_local_llm, _run_cloud_agent_async,
            _get_knowledge_context, get_episodic_memory_manager, get_distillation_engine
        )
    except ImportError:
        # Fallback to original
        from ai_core import run_smart_agent_async
        return await run_smart_agent_async(
            prompt, expert_name, category, require_cot, is_critical, images,
            session_id, local_router, is_vip, project_context
        )

    # Phase 1: Prepare prompt
    memory_crystals = await load_memory_crystals(project_context)
    prompt = audit_efficiency(prompt)
    is_threat, _ = check_threats(prompt)
    if is_threat:
        return "[SECURITY] Prompt rejected"
    prompt = inject_anti_hallucination(prompt, expert_name)
    if memory_crystals:
        prompt = memory_crystals + "\n" + prompt

    # Phase 2: Load context
    project_context = (project_context or _os.getenv("MAIN_PROJECT", "atra-web-ide")).strip()
    user_part = prompt.split("Запрос:")[-1].strip() if "Запрос:" in prompt else prompt
    contexts = await inject_context_enrichment(expert_name, user_part, project_context)
    knowledge = await _get_knowledge_context(prompt, project_context)

    # Phase 3: Call LLM
    router = _get_local_router()
    try:
        response, source = await _call_llm_with_router(
            prompt, expert_name, category, is_vip, local_router or router
        )
    except Exception:
        response = await _run_cloud_agent_async(prompt, category=category, is_vip=is_vip)
        source = "cloud"

    if not response:
        response = "[SYSTEM: LLM unavailable]"
        source = "error"

    # Phase 4: Process response
    response = clean_response(response)
    response = strip_think_blocks(response)

    logger.info(f"[V2] {expert_name} → {source} ({len(response)} chars, {time.time()-start:.1f}s)")
    return response


async def _call_llm_with_router(
    prompt: str, expert_name: str, category: _Optional[str],
    is_vip: bool, router
) -> tuple:
    """Try local router first, then fallback."""
    if router:
        result = await router.run_local_llm(prompt, category=category, expert_name=expert_name)
        if result and len(str(result)) > 10:
            return result, "local"
    from ai_core import _run_cloud_agent_async
    result = await _run_cloud_agent_async(prompt, category=category, is_vip=is_vip)
    return result, "cloud"
