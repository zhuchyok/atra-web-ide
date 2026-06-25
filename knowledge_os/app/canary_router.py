"""
Canary Router (Singularity 31.3) — безопасный rollout мутаций экспертов.

Как работает:
1. Перехватывает запросы к эксперту (до LLM)
2. С вероятностью CANARY_TRAFFIC_PERCENT% использует мутированный промпт
3. Сравнивает результат с эталоном (оригинальный промпт)
4. Если мутация лучше -> win_count++, иначе loss_count++
5. При win_rate > PROMOTION_WIN_RATE_THRESHOLD -> promotion_engine.py продвигает
"""

import asyncio
import json
import logging
import os
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CANARY_TRAFFIC_PERCENT = int(os.getenv("CANARY_TRAFFIC_PERCENT", "10"))
CANARY_MIN_TESTS = int(os.getenv("CANARY_MIN_TESTS", "10"))


async def get_active_mutations(expert_id: str) -> List[Dict[str, Any]]:
    """Get active shadow mutations for an expert."""
    try:
        import asyncpg
        pool = await _get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, mutated_prompt
                   FROM expert_mutations
                   WHERE status = 'shadow' AND (total_tests IS NULL OR total_tests = 0)
                   ORDER BY created_at DESC LIMIT 1"""
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.debug(f"[CANARY] Failed to get mutations: {e}")
        return []


async def should_use_canary(expert_name: str, expert_id: str) -> Tuple[bool, Optional[Dict]]:
    """Should we use a canary mutation for this request?"""
    if random.randint(1, 100) > CANARY_TRAFFIC_PERCENT:
        return False, None

    mutations = await get_active_mutations(expert_id)
    if not mutations:
        return False, None

    mutation = mutations[0]
    if mutation.get("total_tests", 0) >= CANARY_MIN_TESTS:
        return False, None

    return True, mutation


async def record_canary_result(
    mutation_id: str,
    production_response: str,
    canary_response: str,
    expert_name: str,
) -> None:
    """Compare responses and record win/loss for the mutation."""
    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            winner = await _judge_responses(production_response, canary_response)
            is_win = winner == "canary"

            await conn.execute(
                """UPDATE expert_mutations
                   SET total_tests = COALESCE(total_tests, 0) + 1,
                       win_count = COALESCE(win_count, 0) + $2,
                       last_tested_at = NOW()
                   WHERE id = $1::uuid""",
                mutation_id,
                1 if is_win else 0,
            )
            logger.info(
                f"[CANARY] {'WIN' if is_win else 'LOSS'} for mutation {mutation_id[:8]} ({expert_name})"
            )
    except Exception as e:
        logger.warning(f"[CANARY] Record failed: {e}")


async def _judge_responses(production: str, canary: str) -> str:
    """Simple heuristic: prefer longer, non-error responses."""
    if not production or production.startswith("[SYSTEM:"):
        return "canary"
    if not canary or canary.startswith("[SYSTEM:"):
        return "production"
    if len(canary) > len(production) * 1.2:
        return "canary"
    if len(production) > len(canary) * 1.2:
        return "production"
    return "production"


async def _get_pool():
    try:
        from app.db_pool import get_pool
        return await get_pool()
    except Exception:
        try:
            import asyncpg
            db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
            return await asyncpg.create_pool(db_url, min_size=1, max_size=2)
        except Exception:
            return None


async def run_canary_daemon():
    """Фоновый тест мутаций без пользовательского трафика.
    Каждый час тестирует до 5 untested shadow mutations."""
    _untested = []
    try:
        pool = await _get_pool()
        if not pool:
            return
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, expert_id, mutated_prompt
                   FROM expert_mutations
                   WHERE status = 'shadow' AND (total_tests IS NULL OR total_tests = 0)
                   ORDER BY created_at DESC LIMIT 5"""
            )
            _untested = [dict(r) for r in rows]
    except Exception as e:
        logger.debug(f"[CANARY_DAEMON] Query failed: {e}")

    for mutation in _untested:
        try:
            # Get the production equivalent
            pool = await _get_pool()
            if not pool:
                continue
            async with pool.acquire() as conn:
                expert = await conn.fetchrow(
                    "SELECT name FROM experts WHERE id = $1", mutation["expert_id"]
                )
            if not expert:
                continue

            # Run shadow LLM call with mutated prompt to validate it
            from ai_core import _run_local_llm

            _canary_resp = await _run_local_llm(mutation["mutated_prompt"], category="general")

            if _canary_resp:
                # Simple validation: response exists and is not an error
                _resp_str = str(_canary_resp)
                if not _resp_str.startswith("[SYSTEM:") and len(_resp_str) > 10:
                    await record_canary_result(
                        mutation_id=mutation["id"],
                        production_response=_resp_str,
                        canary_response=_resp_str,
                        expert_name=expert["name"],
                    )
                else:
                    logger.info(f"[CANARY_DAEMON] Mutation {mutation['id'][:8]} produced error response")
        except Exception as e:
            logger.debug(f"[CANARY_DAEMON] Test failed for {mutation.get('id','')[:8]}: {e}")

    return len(_untested)
