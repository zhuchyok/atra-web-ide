import asyncio
import json
import logging
import math
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import asyncpg
except ImportError:
    asyncpg = None

logger = logging.getLogger(__name__)

# Thresholds for promotion (configurable; production defaults keep safety-first posture)
MIN_TESTS = int(os.getenv("PROMOTION_MIN_TESTS", "10"))
MIN_WIN_COUNT = int(os.getenv("PROMOTION_MIN_WIN_COUNT", "6"))
WIN_RATE_THRESHOLD = float(os.getenv("PROMOTION_WIN_RATE_THRESHOLD", "0.65"))
MIN_LOWER_BOUND = float(os.getenv("PROMOTION_MIN_LOWER_BOUND", "0.50"))
WILSON_Z = float(os.getenv("PROMOTION_WILSON_Z", "1.96"))
PROMOTION_REPORT_INTERVAL_HOURS = int(os.getenv("PROMOTION_REPORT_INTERVAL_HOURS", "6"))
PROMOTION_REPORT_WINDOW_HOURS = int(os.getenv("PROMOTION_REPORT_WINDOW_HOURS", "24"))


def _wilson_lower_bound(wins: int, total: int, z: float = WILSON_Z) -> float:
    """Lower confidence bound for Bernoulli success rate."""
    if total <= 0:
        return 0.0
    phat = wins / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = phat + z2 / (2.0 * total)
    margin = z * math.sqrt((phat * (1.0 - phat) + z2 / (4.0 * total)) / total)
    return max(0.0, (center - margin) / denom)


async def get_db_pool():
    if asyncpg is None:
        return None
    # Try to use existing pool if available from other modules, or create new
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
    return await asyncpg.create_pool(db_url, min_size=1, max_size=5)


async def check_and_promote_mutations(conn: Optional[asyncpg.Connection] = None):
    """
    Queries expert_mutations for active 'shadow' mutations and promotes them if they meet thresholds.
    Can accept an existing connection or create its own pool.
    """
    logger.info("🚀 Starting Shadow Prompt Promotion Engine...")

    should_close_conn = False
    pool = None
    if conn is None:
        pool = await get_db_pool()
        if not pool:
            logger.error("❌ asyncpg not installed or pool not available.")
            return
        conn = await pool.acquire()
        should_close_conn = True

    summary: Dict[str, Any] = {
        "scanned": 0,
        "promoted": 0,
        "shadow_backlog": 0,
        "gate_reasons": {
            "insufficient_tests": 0,
            "insufficient_wins": 0,
            "insufficient_win_rate": 0,
            "insufficient_confidence": 0,
        },
    }

    try:
        # 1. Query active shadow mutations and evaluate gate per candidate.
        mutations = await conn.fetch(
            """
            SELECT id, expert_id, mutated_prompt, win_count, total_tests, base_version
            FROM expert_mutations
            WHERE status = 'shadow'
            ORDER BY created_at ASC
            LIMIT 200
        """
        )
        summary["scanned"] = len(mutations)
        summary["shadow_backlog"] = len(mutations)

        promoted_count = 0
        for mut in mutations:
            total = mut["total_tests"]
            win_count = mut["win_count"]
            win_rate = win_count / total if total > 0 else 0

            lower_bound = _wilson_lower_bound(win_count, total)

            if (
                total >= MIN_TESTS
                and win_count >= MIN_WIN_COUNT
                and win_rate >= WIN_RATE_THRESHOLD
                and lower_bound >= MIN_LOWER_BOUND
            ):
                logger.info(
                    "🌟 Promoting mutation %s for expert %s (win_rate=%.2f%%, lower_bound=%.2f%%, tests=%s)",
                    mut["id"],
                    mut["expert_id"],
                    win_rate * 100.0,
                    lower_bound * 100.0,
                    total,
                )

                async with conn.transaction():
                    # A. Update expert's system prompt and version
                    # We check if 'version' column exists in experts table (it should based on Task 4 requirements)
                    await conn.execute(
                        """
                        UPDATE experts
                        SET system_prompt = $1,
                            version = COALESCE(version, 0) + 1
                        WHERE id = $2
                    """,
                        mut["mutated_prompt"],
                        mut["expert_id"],
                    )

                    # B. Update this mutation's status to 'promoted'
                    await conn.execute(
                        """
                        UPDATE expert_mutations
                        SET status = 'promoted',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                    """,
                        mut["id"],
                    )

                    # C. Archive other shadow mutations for the same expert
                    await conn.execute(
                        """
                        UPDATE expert_mutations
                        SET status = 'archived',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE expert_id = $1 AND id != $2 AND status = 'shadow'
                    """,
                        mut["expert_id"],
                        mut["id"],
                    )

                    # D. Log the promotion as an 'architectural_lesson' to knowledge_nodes
                    expert_info = await conn.fetchrow(
                        "SELECT name FROM experts WHERE id = $1", mut["expert_id"]
                    )
                    expert_name = expert_info["name"] if expert_info else str(mut["expert_id"])

                    content = (
                        f"Architectural Lesson: Expert '{expert_name}' system prompt was evolved and promoted. "
                        f"The new prompt achieved a {win_rate:.2%} win rate over {total} shadow tests. "
                        f"Mutation ID: {mut['id']}."
                    )

                    metadata = json.dumps(
                        {
                            "type": "architectural_lesson",
                            "subtype": "prompt_promotion",
                            "expert_id": str(mut["expert_id"]),
                            "expert_name": expert_name,
                            "mutation_id": str(mut["id"]),
                            "win_rate": win_rate,
                            "wilson_lower_bound": lower_bound,
                            "total_tests": total,
                            "base_version": mut["base_version"],
                            "promotion_thresholds": {
                                "min_tests": MIN_TESTS,
                                "min_win_count": MIN_WIN_COUNT,
                                "win_rate_threshold": WIN_RATE_THRESHOLD,
                                "min_lower_bound": MIN_LOWER_BOUND,
                            },
                            "promoted_at": datetime.now().isoformat(),
                        }
                    )

                    # Try to find a 'System' or 'Meta' domain, fallback to first available
                    domain_id = await conn.fetchval(
                        "SELECT id FROM domains WHERE name IN ('System', 'Meta', 'AI') LIMIT 1"
                    )
                    if not domain_id:
                        domain_id = await conn.fetchval("SELECT id FROM domains LIMIT 1")

                    await conn.execute(
                        """
                        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, source_ref)
                        VALUES ($1, $2, 1.0, $3, TRUE, 'promotion_engine')
                    """,
                        domain_id,
                        content,
                        metadata,
                    )

                promoted_count += 1
            else:
                if total < MIN_TESTS:
                    summary["gate_reasons"]["insufficient_tests"] += 1
                if win_count < MIN_WIN_COUNT:
                    summary["gate_reasons"]["insufficient_wins"] += 1
                if win_rate < WIN_RATE_THRESHOLD:
                    summary["gate_reasons"]["insufficient_win_rate"] += 1
                if lower_bound < MIN_LOWER_BOUND:
                    summary["gate_reasons"]["insufficient_confidence"] += 1
                logger.info(
                    "⏸️ Mutation %s not promoted: tests=%s wins=%s win_rate=%.2f%% lower_bound=%.2f%% "
                    "(needs tests>=%s, wins>=%s, win_rate>=%.2f%%, lower_bound>=%.2f%%)",
                    mut["id"],
                    total,
                    win_count,
                    win_rate * 100.0,
                    lower_bound * 100.0,
                    MIN_TESTS,
                    MIN_WIN_COUNT,
                    WIN_RATE_THRESHOLD * 100.0,
                    MIN_LOWER_BOUND * 100.0,
                )

        if promoted_count > 0:
            logger.info(f"✅ Promotion cycle finished. Promoted {promoted_count} mutations.")
        else:
            logger.info("ℹ️ No mutations met promotion thresholds this cycle.")
        summary["promoted"] = promoted_count

    finally:
        if should_close_conn and conn:
            await pool.release(conn)
            await pool.close()

    return summary


async def _emit_rollout_report_if_due(summary: Dict[str, Any]) -> None:
    """Persist periodic shadow->promoted rollout report for observability."""
    pool = await get_db_pool()
    if not pool:
        return

    try:
        async with pool.acquire() as conn:
            should_emit = await conn.fetchval(
                """
                SELECT NOT EXISTS (
                    SELECT 1
                    FROM knowledge_nodes
                    WHERE metadata->>'type' = 'mutation_rollout_report'
                      AND created_at > NOW() - make_interval(hours => $1::int)
                )
                """,
                PROMOTION_REPORT_INTERVAL_HOURS,
            )
            if not should_emit:
                return

            window_hours = max(1, PROMOTION_REPORT_WINDOW_HOURS)
            promoted_24h = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM expert_mutations
                WHERE status = 'promoted'
                  AND COALESCE(updated_at, created_at) > NOW() - make_interval(hours => $1::int)
                """,
                window_hours,
            )
            shadow_24h = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM expert_mutations
                WHERE status = 'shadow'
                  AND created_at > NOW() - make_interval(hours => $1::int)
                """,
                window_hours,
            )
            archived_24h = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM expert_mutations
                WHERE status = 'archived'
                  AND COALESCE(updated_at, created_at) > NOW() - make_interval(hours => $1::int)
                """,
                window_hours,
            )
            backlog_shadow = await conn.fetchval(
                "SELECT COUNT(*) FROM expert_mutations WHERE status = 'shadow'"
            )

            promoted_24h = int(promoted_24h or 0)
            shadow_24h = int(shadow_24h or 0)
            archived_24h = int(archived_24h or 0)
            backlog_shadow = int(backlog_shadow or 0)
            denom = promoted_24h + shadow_24h + archived_24h
            conversion = (promoted_24h / denom) if denom > 0 else 0.0

            gate_reasons = summary.get("gate_reasons") or {}
            report_text = (
                "📊 MUTATION ROLLOUT REPORT\n"
                f"- window_hours: {window_hours}\n"
                f"- promoted: {promoted_24h}\n"
                f"- shadow_created: {shadow_24h}\n"
                f"- archived: {archived_24h}\n"
                f"- shadow_backlog: {backlog_shadow}\n"
                f"- conversion_rate: {conversion:.2%}\n"
                f"- gate_reasons: {gate_reasons}\n"
                f"- thresholds: tests>={MIN_TESTS}, wins>={MIN_WIN_COUNT}, "
                f"win_rate>={WIN_RATE_THRESHOLD:.2f}, lower_bound>={MIN_LOWER_BOUND:.2f}\n"
            )

            report_generated_at = datetime.now().isoformat()
            metadata = {
                "source": "promotion_engine",
                "type": "mutation_rollout_report",
                "window_hours": window_hours,
                "promoted": promoted_24h,
                "shadow_created": shadow_24h,
                "archived": archived_24h,
                "shadow_backlog": backlog_shadow,
                "conversion_rate": conversion,
                "gate_reasons": gate_reasons,
                "thresholds": {
                    "min_tests": MIN_TESTS,
                    "min_win_count": MIN_WIN_COUNT,
                    "win_rate_threshold": WIN_RATE_THRESHOLD,
                    "min_lower_bound": MIN_LOWER_BOUND,
                },
                "report_generated_at": report_generated_at,
                "distilled": "true",
                "distill_status": "done",
                "distilled_by": "system:promotion_engine",
                "distill_rework_reason": "pre_distilled_mutation_rollout_report",
                "distill_completed_at": int(datetime.now().timestamp()),
            }

            domain_id = await conn.fetchval(
                "SELECT id FROM domains WHERE name IN ('System', 'Meta', 'AI') LIMIT 1"
            )
            if not domain_id:
                domain_id = await conn.fetchval("SELECT id FROM domains LIMIT 1")
            if not domain_id:
                return

            await conn.execute(
                """
                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, source_ref)
                VALUES ($1, $2, 1.0, $3::jsonb, TRUE, 'promotion_engine_report')
                """,
                domain_id,
                report_text,
                json.dumps(metadata),
            )
            logger.info("📊 Rollout report emitted (window=%sh)", window_hours)
    finally:
        await pool.close()


async def run_promotion_cycle():
    """Entry point for nightly learner or manual trigger."""
    try:
        summary = await check_and_promote_mutations()
        await _emit_rollout_report_if_due(summary or {})
    except Exception as e:
        logger.error(f"❌ Error in promotion cycle: {e}", exc_info=True)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(run_promotion_cycle())
