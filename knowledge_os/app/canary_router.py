"""
Canary Router (Singularity 31.3) — безопасный rollout мутаций экспертов.

Как работает:
1. С вероятностью CANARY_TRAFFIC_PERCENT% после ответа продакшена гоняет shadow-промпт
2. Сравнивает результат с эталоном (оригинальный ответ / prod prompt)
3. Если мутация лучше -> win_count++, иначе loss_count++
4. При win_rate > PROMOTION_WIN_RATE_THRESHOLD -> promotion_engine.py продвигает
"""

from __future__ import annotations

import json
import logging
import os
import random
from typing import Any

logger = logging.getLogger(__name__)

CANARY_TRAFFIC_PERCENT = int(os.getenv("CANARY_TRAFFIC_PERCENT", "10"))
CANARY_MIN_TESTS = int(os.getenv("CANARY_MIN_TESTS", "10"))
CANARY_PROBE_QUERY = os.getenv(
    "CANARY_PROBE_QUERY",
    "In 5 short bullets, state your top responsibilities and one risk you always check.",
)


async def get_active_mutations(expert_id: str) -> list[dict[str, Any]]:
    """Active shadow mutations for this expert that still need tests."""
    try:
        pool = await _get_pool()
        if not pool:
            return []
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, mutated_prompt, COALESCE(total_tests, 0) AS total_tests
                FROM expert_mutations
                WHERE status = 'shadow'
                  AND expert_id = $1::uuid
                  AND COALESCE(total_tests, 0) < $2
                ORDER BY created_at DESC
                LIMIT 1
                """,
                str(expert_id),
                CANARY_MIN_TESTS,
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.debug(f"[CANARY] Failed to get mutations: {e}")
        return []


async def should_use_canary(expert_name: str, expert_id: str) -> tuple[bool, dict[str, Any] | None]:
    """Should we use a canary mutation for this request?"""
    if random.randint(1, 100) > CANARY_TRAFFIC_PERCENT:
        return False, None

    mutations = await get_active_mutations(expert_id)
    if not mutations:
        return False, None

    mutation = mutations[0]
    if int(mutation.get("total_tests") or 0) >= CANARY_MIN_TESTS:
        return False, None

    return True, mutation


async def record_canary_result(
    mutation_id: str,
    production_response: str,
    canary_response: str,
    expert_name: str,
    query: str | None = None,
) -> None:
    """Compare responses and record win/loss + battle log for Prompt Battle UI."""
    try:
        pool = await _get_pool()
        if not pool:
            return
        winner = await _judge_responses(production_response, canary_response)
        is_win = winner == "canary"
        is_draw = winner == "draw"
        verdict = "Win" if is_win else ("Draw" if is_draw else "Loss")
        reason = f"canary_heuristic winner={winner}"

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE expert_mutations
                SET total_tests = COALESCE(total_tests, 0) + 1,
                    win_count = COALESCE(win_count, 0) + $2,
                    loss_count = COALESCE(loss_count, 0) + $3,
                    draw_count = COALESCE(draw_count, 0) + $4,
                    updated_at = NOW()
                WHERE id = $1::uuid
                """,
                str(mutation_id),
                1 if is_win else 0,
                0 if is_win or is_draw else 1,
                1 if is_draw else 0,
            )
            expert_id = await conn.fetchval(
                "SELECT expert_id FROM expert_mutations WHERE id = $1::uuid",
                str(mutation_id),
            )
            meta = {
                "shadow_execution": "true",
                "shadow_verdict": verdict,
                "shadow_reason": reason,
                "shadow_response": (canary_response or "")[:4000],
                "production_response": (production_response or "")[:2000],
                "mutation_id": str(mutation_id),
                "source": "canary_router",
                "expert_name": expert_name,
            }
            await conn.execute(
                """
                INSERT INTO interaction_logs (expert_id, user_query, assistant_response, metadata)
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                expert_id,
                (query or CANARY_PROBE_QUERY)[:2000],
                (canary_response or "")[:8000] or "(empty shadow)",
                json.dumps(meta, ensure_ascii=False),
            )
        logger.info(f"[CANARY] {verdict} for mutation {str(mutation_id)[:8]} ({expert_name})")
    except Exception as e:
        logger.warning(f"[CANARY] Record failed: {e}")


async def _judge_responses(production: str, canary: str) -> str:
    """Simple heuristic: prefer longer, non-error responses. Returns canary|production|draw."""
    if not production or production.startswith("[SYSTEM:"):
        return "canary"
    if not canary or canary.startswith("[SYSTEM:"):
        return "production"
    # Same payload = invalid A/B (old daemon bug) → draw, not fake win
    if production.strip() == canary.strip():
        return "draw"
    if len(canary) > len(production) * 1.2:
        return "canary"
    if len(production) > len(canary) * 1.2:
        return "production"
    return "draw"


async def _get_pool():
    try:
        from app.db_pool import get_pool

        return await get_pool()
    except Exception:
        try:
            import asyncpg

            # Default matches local docker PgBouncer; override via DATABASE_URL.
            db_url = os.getenv(
                "DATABASE_URL",
                "postgresql://admin:secret@localhost:6432/knowledge_os",  # pragma: allowlist secret
            )
            return await asyncpg.create_pool(db_url, min_size=1, max_size=2)
        except Exception:
            return None


async def _run_llm(prompt: str) -> str:
    """Best-effort local LLM call for daemon probes."""
    try:
        try:
            from app.ai_core import _run_local_llm
        except ImportError:
            from ai_core import _run_local_llm  # type: ignore

        res = await _run_local_llm(prompt, category="general")
        return str(res[0] if isinstance(res, tuple) else res)
    except Exception as e:
        logger.debug(f"[CANARY_DAEMON] LLM failed: {e}")
        return ""


async def run_canary_daemon(limit: int = 5) -> int:
    """Фоновый тест shadow-мутаций: prod prompt vs mutated prompt на одном probe."""
    rows: list[dict[str, Any]] = []
    try:
        pool = await _get_pool()
        if not pool:
            return 0
        async with pool.acquire() as conn:
            fetched = await conn.fetch(
                """
                SELECT m.id, m.expert_id, m.mutated_prompt, e.name AS expert_name, e.system_prompt
                FROM expert_mutations m
                JOIN experts e ON e.id = m.expert_id
                WHERE m.status = 'shadow'
                  AND COALESCE(m.total_tests, 0) < $1
                ORDER BY COALESCE(m.total_tests, 0) ASC, m.created_at DESC
                LIMIT $2
                """,
                CANARY_MIN_TESTS,
                limit,
            )
            rows = [dict(r) for r in fetched]
    except Exception as e:
        logger.warning(f"[CANARY_DAEMON] Query failed: {e}")
        return 0

    tested = 0
    for mutation in rows:
        try:
            prod_prompt = (
                f"{mutation.get('system_prompt') or ''}\n\nUSER REQUEST: {CANARY_PROBE_QUERY}"
            )
            shadow_prompt = (
                f"{mutation.get('mutated_prompt') or ''}\n\nUSER REQUEST: {CANARY_PROBE_QUERY}"
            )
            prod_resp = await _run_llm(prod_prompt)
            shadow_resp = await _run_llm(shadow_prompt)
            if not shadow_resp or shadow_resp.startswith("[SYSTEM:"):
                logger.info(
                    f"[CANARY_DAEMON] Mutation {str(mutation['id'])[:8]} produced error response"
                )
                continue
            # If prod LLM failed, still record with short stub so counters move
            if not prod_resp or prod_resp.startswith("[SYSTEM:"):
                prod_resp = "(production probe unavailable)"

            await record_canary_result(
                mutation_id=str(mutation["id"]),
                production_response=prod_resp,
                canary_response=shadow_resp,
                expert_name=mutation.get("expert_name") or "unknown",
                query=CANARY_PROBE_QUERY,
            )
            tested += 1
        except Exception as e:
            logger.debug(f"[CANARY_DAEMON] Test failed for {str(mutation.get('id', ''))[:8]}: {e}")

    return tested
