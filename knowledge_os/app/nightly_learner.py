"""
[SINGULARITY] Nightly learner entrypoint.

Runs in the background:
- Continuous distillation (independent asyncio task)
- Nightly cycle (self-learning, evolution, promotion, mentorship) every 24h

Also provides helpers used by orchestrators / scripts:
`create_debate_for_hypothesis`, `run_expert_council` (re-export).
"""

import asyncio
import json
import logging
import os
from typing import Optional

import asyncpg
from distillation_tail_metrics import get_distill_eligible_now
from nightly_expert_council import run_expert_council, run_nightly_council_phase

# Re-export for scripts: create_debates_for_existing / test_expert_council
__all__ = [
    "create_debate_for_hypothesis",
    "run_expert_council",
    "run_nightly_council_phase",
    "run_nightly_cycle",
    "main_loop",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", force=True)
logger = logging.getLogger(__name__)

# Suppress noisy HTTP client logs so [NIGHTLY] markers stay visible
for _lib in ("httpx", "httpcore", "urllib3"):
    logging.getLogger(_lib).setLevel(logging.WARNING)

DB_URL = os.getenv(
    "DATABASE_URL", "postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os"
)
NIGHTLY_INTERVAL_SEC = int(os.getenv("NIGHTLY_INTERVAL_SEC", "86400"))  # 24h by default
NIGHTLY_DISTILL_TARGET_ELIGIBLE = int(os.getenv("NIGHTLY_DISTILL_TARGET_ELIGIBLE", "5"))
NIGHTLY_DISTILL_MAX_ROUNDS = int(os.getenv("NIGHTLY_DISTILL_MAX_ROUNDS", "6"))
NIGHTLY_DISTILL_ROUND_DELAY_SEC = int(os.getenv("NIGHTLY_DISTILL_ROUND_DELAY_SEC", "2"))
NIGHTLY_DISTILL_TURBO_HIGH_WATERMARK = int(os.getenv("NIGHTLY_DISTILL_TURBO_HIGH_WATERMARK", "12"))
NIGHTLY_DISTILL_TURBO_MAX_ROUNDS = int(os.getenv("NIGHTLY_DISTILL_TURBO_MAX_ROUNDS", "10"))
NIGHTLY_DISTILL_STAGNANT_LIMIT = int(os.getenv("NIGHTLY_DISTILL_STAGNANT_LIMIT", "2"))
NIGHTLY_DISTILL_TURBO_ENTER_WATERMARK = int(
    os.getenv("NIGHTLY_DISTILL_TURBO_ENTER_WATERMARK", str(NIGHTLY_DISTILL_TURBO_HIGH_WATERMARK))
)
NIGHTLY_DISTILL_TURBO_EXIT_WATERMARK = int(
    os.getenv(
        "NIGHTLY_DISTILL_TURBO_EXIT_WATERMARK", str(max(NIGHTLY_DISTILL_TARGET_ELIGIBLE + 1, 8))
    )
)
NIGHTLY_DISTILL_TURBO_ENTER_STREAK = int(os.getenv("NIGHTLY_DISTILL_TURBO_ENTER_STREAK", "2"))
NIGHTLY_DISTILL_TURBO_EXIT_STREAK = int(os.getenv("NIGHTLY_DISTILL_TURBO_EXIT_STREAK", "2"))
NIGHTLY_DISTILL_FORCE_MODE = os.getenv("NIGHTLY_DISTILL_FORCE_MODE", "auto").strip().lower()
_DISTILLER_SINGLETON = None
_DISTILL_MODE = "normal"
_DISTILL_HIGH_STREAK = 0
_DISTILL_LOW_STREAK = 0


def _get_distiller_singleton():
    global _DISTILLER_SINGLETON
    if _DISTILLER_SINGLETON is None:
        from distillation_engine import KnowledgeDistiller

        _DISTILLER_SINGLETON = KnowledgeDistiller()
    return _DISTILLER_SINGLETON


def _select_distill_mode(eligible_now: int, target: int) -> tuple[str, str]:
    """
    Adaptive mode selection with hysteresis to avoid normal/turbo flapping.
    """
    global _DISTILL_MODE, _DISTILL_HIGH_STREAK, _DISTILL_LOW_STREAK

    if NIGHTLY_DISTILL_FORCE_MODE in {"normal", "turbo"}:
        forced = NIGHTLY_DISTILL_FORCE_MODE
        _DISTILL_MODE = forced
        _DISTILL_HIGH_STREAK = 0
        _DISTILL_LOW_STREAK = 0
        return forced, "forced_mode"

    enter_mark = max(target + 1, NIGHTLY_DISTILL_TURBO_ENTER_WATERMARK)
    exit_mark = max(target, min(enter_mark - 1, NIGHTLY_DISTILL_TURBO_EXIT_WATERMARK))
    enter_streak_need = max(1, NIGHTLY_DISTILL_TURBO_ENTER_STREAK)
    exit_streak_need = max(1, NIGHTLY_DISTILL_TURBO_EXIT_STREAK)

    if eligible_now >= enter_mark:
        _DISTILL_HIGH_STREAK += 1
        _DISTILL_LOW_STREAK = 0
    elif eligible_now <= exit_mark:
        _DISTILL_LOW_STREAK += 1
        _DISTILL_HIGH_STREAK = 0
    else:
        _DISTILL_HIGH_STREAK = 0
        _DISTILL_LOW_STREAK = 0

    if _DISTILL_MODE != "turbo" and _DISTILL_HIGH_STREAK >= enter_streak_need:
        _DISTILL_MODE = "turbo"
        _DISTILL_HIGH_STREAK = 0
        return _DISTILL_MODE, "enter_turbo_hysteresis"

    if _DISTILL_MODE == "turbo" and _DISTILL_LOW_STREAK >= exit_streak_need:
        _DISTILL_MODE = "normal"
        _DISTILL_LOW_STREAK = 0
        return _DISTILL_MODE, "exit_turbo_hysteresis"

    return _DISTILL_MODE, "steady"


async def run_distillation_until_target() -> None:
    """
    Run several distillation rounds in one nightly cycle to keep eligible tail low.
    Guardrails:
    - hard cap on rounds
    - stop on repeated non-improvement
    """
    distiller = _get_distiller_singleton()
    base_max_rounds = max(1, NIGHTLY_DISTILL_MAX_ROUNDS)
    target = max(0, NIGHTLY_DISTILL_TARGET_ELIGIBLE)
    delay_sec = max(0, NIGHTLY_DISTILL_ROUND_DELAY_SEC)
    stagnant_limit = max(1, NIGHTLY_DISTILL_STAGNANT_LIMIT)

    conn: Optional[asyncpg.Connection] = None
    try:
        conn = await asyncpg.connect(DB_URL)
        eligible_now = await get_distill_eligible_now(conn)
        distill_mode, mode_reason = _select_distill_mode(eligible_now, target)
        turbo_mode = distill_mode == "turbo"
        max_rounds = (
            max(base_max_rounds, NIGHTLY_DISTILL_TURBO_MAX_ROUNDS)
            if turbo_mode
            else base_max_rounds
        )
        logger.info(
            "⚗️ [NIGHTLY] Distillation drain start: eligible_now=%s target=%s mode=%s reason=%s max_rounds=%s",
            eligible_now,
            target,
            distill_mode,
            mode_reason,
            max_rounds,
        )

        stagnant_rounds = 0
        for round_no in range(1, max_rounds + 1):
            if eligible_now <= target:
                logger.info(
                    "✅ [NIGHTLY] Distillation target reached early: eligible_now=%s (target=%s)",
                    eligible_now,
                    target,
                )
                return

            before = eligible_now
            await distiller.distill_knowledge_batch()
            if delay_sec:
                await asyncio.sleep(delay_sec)
            eligible_now = await get_distill_eligible_now(conn)
            logger.info(
                "⚗️ [NIGHTLY] Distillation round %s/%s: eligible %s -> %s",
                round_no,
                max_rounds,
                before,
                eligible_now,
            )

            if eligible_now >= before:
                stagnant_rounds += 1
                if stagnant_rounds >= stagnant_limit:
                    logger.warning(
                        "⚠️ [NIGHTLY] Distillation stagnated for %s rounds (limit=%s), stopping early.",
                        stagnant_rounds,
                        stagnant_limit,
                    )
                    break
            else:
                stagnant_rounds = 0

        logger.info(
            "✅ [NIGHTLY] Distillation drain finished: eligible_now=%s target=%s",
            eligible_now,
            target,
        )
    finally:
        if conn:
            await conn.close()


async def create_debate_for_hypothesis(
    conn: asyncpg.Connection,
    knowledge_node_id: str,
    hypothesis_text: str,
    domain_id: Optional[str] = None,
) -> Optional[str]:
    """
    Run Expert Council on a hypothesis and also enqueue a verification task.
    Restores pre-8.2 behavior (council nodes for Wisdom tab) + task hook.
    """
    expert = None
    if domain_id:
        try:
            expert = await conn.fetchrow(
                "SELECT id FROM experts WHERE domain_id = $1 ORDER BY RANDOM() LIMIT 1",
                domain_id,
            )
        except Exception:
            expert = None
    if not expert and domain_id:
        try:
            domain = await conn.fetchrow("SELECT name FROM domains WHERE id = $1", domain_id)
            if domain:
                expert = await conn.fetchrow(
                    "SELECT id FROM experts WHERE department = $1 ORDER BY RANDOM() LIMIT 1",
                    domain["name"],
                )
        except Exception:
            expert = None
    if not expert:
        expert = await conn.fetchrow("SELECT id FROM experts ORDER BY RANDOM() LIMIT 1")

    council_node_id = None
    if expert:
        try:
            council_node_id = await run_expert_council(
                conn, knowledge_node_id, hypothesis_text, expert["id"]
            )
        except Exception as exc:
            logger.warning("create_debate_for_hypothesis council failed: %s", exc)
    else:
        logger.warning("No experts found for hypothesis debate, skipping council")

    title = f"Debate hypothesis {str(knowledge_node_id)[:8]}"
    metadata = {
        "source": "nightly_hypothesis_debate",
        "hypothesis_node_id": str(knowledge_node_id),
        "council_node_id": council_node_id,
        "is_verification": True,
        "priority": "high",
        "required_capabilities": ["verification", "analysis"],
    }
    description = (
        "Проведи критический разбор гипотезы, оцени техническую состоятельность, риски и применимость.\n\n"
        f"Гипотеза:\n{hypothesis_text}"
    )

    try:
        task_id = await conn.fetchval(
            """
            INSERT INTO tasks (title, description, status, priority, domain_id, metadata)
            VALUES ($1, $2, 'pending', 'high', $3, $4::jsonb)
            RETURNING id
            """,
            title,
            description,
            domain_id,
            json.dumps(metadata, ensure_ascii=False),
        )
        return str(task_id) if task_id else council_node_id
    except Exception:
        task_id = await conn.fetchval(
            """
            INSERT INTO tasks (title, description, status, priority, metadata)
            VALUES ($1, $2, 'pending', 'high', $3::jsonb)
            RETURNING id
            """,
            title,
            description,
            json.dumps(metadata, ensure_ascii=False),
        )
        return str(task_id) if task_id else council_node_id


async def run_nightly_cycle() -> None:
    logger.info("🌙 [NIGHTLY] Starting nightly cycle...")

    # 1) Self-learning cycle
    try:
        from corporation_self_learning import get_corporation_learner

        learner = get_corporation_learner(DB_URL)
        await learner.run_learning_cycle()
        logger.info("✅ [NIGHTLY] Self-learning cycle completed.")
    except Exception as exc:
        logger.error("❌ [NIGHTLY] Self-learning failed: %s", exc)

    # 2) Expert mutation/evolution cycle
    try:
        from enhanced_expert_evolver import run_enhanced_evolution_cycle

        await run_enhanced_evolution_cycle()
        logger.info("✅ [NIGHTLY] Expert evolution cycle completed.")
    except Exception as exc:
        logger.error("❌ [NIGHTLY] Expert evolution failed: %s", exc)

    # 3) Shadow promotion cycle (if shadow mutations exist)
    try:
        from promotion_engine import run_promotion_cycle

        await run_promotion_cycle()
        logger.info("✅ [NIGHTLY] Mutation promotion cycle completed.")
    except Exception as exc:
        logger.error("❌ [NIGHTLY] Mutation promotion failed: %s", exc)

    # 4) Mentorship and Wisdom cycle (Singularity 20.0)
    try:
        from mentorship_engine import run_mentorship_cycle
        from sop_generator import run_sop_cycle

        await run_mentorship_cycle(limit=5)
        await run_sop_cycle()
        logger.info("✅ [NIGHTLY] Mentorship and SOP cycles completed.")
    except Exception as exc:
        logger.error("❌ [NIGHTLY] Mentorship/SOP cycle failed: %s", exc)

    # 5) Expert Council / Red Team debates → Wisdom tab (restored after 8.2 cleanup)
    try:
        n = await run_nightly_council_phase()
        logger.info("✅ [NIGHTLY] Expert Council phase completed (%s debate node(s)).", n)
    except Exception as exc:
        logger.error("❌ [NIGHTLY] Expert Council phase failed: %s", exc)

    # 6) MetaArchitect guarded code evolution (shadow mutations; cooldown 12h default)
    try:
        from meta_architect import MetaArchitect

        evo = await MetaArchitect().run_guarded_evolution()
        logger.info("✅ [NIGHTLY] MetaArchitect guarded evolution: %s", evo)
    except Exception as exc:
        logger.error("❌ [NIGHTLY] MetaArchitect evolution failed: %s", exc)


async def run_continuous_distillation() -> None:
    """Run distillation continuously as a background task."""
    logger.info("⚗️ [NIGHTLY] Continuous distillation started in background")
    while True:
        await run_distillation_until_target()
        await asyncio.sleep(300)


async def run_continuous_embedding_backfill() -> None:
    """Priority RAG embedding backfill (eligible nodes only). Bounded rate."""
    interval = max(60, int(os.getenv("EMBED_BACKFILL_INTERVAL_SEC", "300")))
    batch = max(5, int(os.getenv("EMBED_BACKFILL_BATCH", "40")))
    enabled = os.getenv("EMBED_BACKFILL_ENABLED", "true").lower() in ("1", "true", "yes")
    logger.info(
        "🧩 [NIGHTLY] Continuous embedding backfill started (enabled=%s batch=%s interval=%ss)",
        enabled,
        batch,
        interval,
    )
    # One-shot junk purge at start (venv/site-packages PROJECT_FILE)
    if enabled:
        try:
            from embedding_eligibility import purge_non_rag_junk

            purged = await purge_non_rag_junk(
                limit=int(os.getenv("EMBED_JUNK_PURGE_LIMIT", "25000"))
            )
            if purged:
                logger.info(
                    "🧹 [NIGHTLY] Purged %s non-RAG junk nodes (venv/site-packages)", purged
                )
        except Exception as exc:
            logger.warning("🧹 [NIGHTLY] Junk purge skipped: %s", exc)

    while True:
        if enabled:
            try:
                from embedding_eligibility import backfill_eligible_embeddings

                stats = await backfill_eligible_embeddings(limit=batch)
                logger.info(
                    "🧩 [NIGHTLY] Embedding backfill: updated=%s failed=%s candidates=%s",
                    stats.get("updated"),
                    stats.get("failed"),
                    stats.get("candidates"),
                )
            except Exception as exc:
                logger.warning("🧩 [NIGHTLY] Embedding backfill failed: %s", exc)
        await asyncio.sleep(interval)


async def run_continuous_priority_redistill() -> None:
    """Small depth pass: re-distill elite wisdom with stronger teacher (bounded)."""
    interval = max(300, int(os.getenv("REDISTILL_PRIORITY_INTERVAL_SEC", "1800")))
    batch = max(1, min(int(os.getenv("REDISTILL_PRIORITY_BATCH", "1")), 10))
    enabled = os.getenv("REDISTILL_PRIORITY_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    logger.info(
        "⚗️ [NIGHTLY] Priority re-distill started (enabled=%s batch=%s interval=%ss)",
        enabled,
        batch,
        interval,
    )
    while True:
        if enabled:
            try:
                from distillation_engine import KnowledgeDistiller

                stats = await KnowledgeDistiller().redistill_priority_batch(limit=batch)
                logger.info(
                    "⚗️ [NIGHTLY] Priority re-distill: updated=%s failed=%s candidates=%s teacher=%s",
                    stats.get("updated"),
                    stats.get("failed"),
                    stats.get("candidates"),
                    stats.get("teacher"),
                )
            except Exception as exc:
                logger.warning("⚗️ [NIGHTLY] Priority re-distill failed: %s", exc)
        await asyncio.sleep(interval)


async def main_loop() -> None:
    """Run nightly cycle periodically with continuous distillation in background."""
    distill_task = asyncio.create_task(run_continuous_distillation())
    embed_task = asyncio.create_task(run_continuous_embedding_backfill())
    redistill_task = asyncio.create_task(run_continuous_priority_redistill())
    logger.info("🌙 [NIGHTLY] Distillation + embedding backfill + priority re-distill running")
    _ = (distill_task, embed_task, redistill_task)

    while True:
        await run_nightly_cycle()
        logger.info(
            "😴 [NIGHTLY] Next cycle in %s sec (%s h).",
            NIGHTLY_INTERVAL_SEC,
            round(NIGHTLY_INTERVAL_SEC / 3600, 2),
        )
        await asyncio.sleep(max(60, NIGHTLY_INTERVAL_SEC))


if __name__ == "__main__":
    asyncio.run(main_loop())
