"""
[SINGULARITY 31.2.2] Orchestrator Phases (modular extraction).

Behavior-preserving extraction from enhanced_orchestrator.py.
Rule: one/few phases at a time → verify → continue. No circular imports:
heavy helpers are injected by the caller.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
from collections.abc import Awaitable
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

PriorityFn = Callable[..., Awaitable[str]]
AssignFn = Callable[..., Awaitable[Any]]
MetricFn = Callable[..., None]


async def phase_0_auto_fix(conn) -> Dict[str, Any]:
    """Phase 0: Auto-fix stuck/unassigned errors before new work."""
    t0 = time.time()
    logger.info("🔧 Phase 0: Auto-fixing errors...")

    phase_result: Any = "skipped"
    try:
        from error_auto_fixer import auto_fix_all_errors

        fix_results = await auto_fix_all_errors(conn)
        if (
            fix_results.get("stuck_tasks_fixed", 0) > 0
            or fix_results.get("unassigned_tasks", 0) > 0
        ):
            phase_result = str(fix_results)
        else:
            phase_result = "ok"
    except ImportError:
        logger.debug("error_auto_fixer module not found, skipping")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Auto-fix error: %s", exc)
        phase_result = str(exc)

    duration_ms = (time.time() - t0) * 1000
    logger.info(
        "[ENHANCED_ORCHESTRATOR] phase=0 duration_ms=%.0f result=%s",
        duration_ms,
        phase_result,
    )
    return {"result": phase_result, "duration_ms": duration_ms}


async def phase_0_5_migrations(conn, *, app_file: str) -> Dict[str, Any]:
    """Phase 0.5: Apply pending SQL migrations from knowledge_os/db/migrations."""
    t05 = time.time()
    logger.info("🗄️ Phase 0.5: Autonomous Migrations...")
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                migration_name VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        base_dir_path = os.path.dirname(os.path.dirname(os.path.abspath(app_file)))
        migration_dir = os.path.join(base_dir_path, "db", "migrations")
        if os.path.exists(migration_dir):
            applied_list = await conn.fetch("SELECT migration_name FROM schema_migrations")
            applied_set = {r["migration_name"] for r in applied_list}
            for file_name in sorted(os.listdir(migration_dir)):
                if not file_name.endswith(".sql"):
                    continue
                if file_name in applied_set:
                    continue
                logger.info("  ⚡ Applying migration: %s", file_name)
                try:
                    with open(os.path.join(migration_dir, file_name), encoding="utf-8") as f:
                        await conn.execute(f.read())
                    await conn.execute(
                        "INSERT INTO schema_migrations (migration_name, applied_at) VALUES ($1, NOW()) ON CONFLICT (migration_name) DO NOTHING",
                        file_name,
                    )
                    logger.info("  ✅ Applied: %s", file_name)
                except Exception as mig_err:  # pylint: disable=broad-exception-caught
                    logger.error("  ❌ Migration %s failed: %s", file_name, mig_err)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Migration error: %s", exc)

    duration_ms = (time.time() - t05) * 1000
    logger.info(
        "[ENHANCED_ORCHESTRATOR] phase=0.5 duration_ms=%.0f result=migrations",
        duration_ms,
    )
    return {"result": "migrations", "duration_ms": duration_ms}


async def ensure_victoria_id(conn) -> Any:
    """Resolve/create Victoria expert id (used by later phases)."""
    victoria_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")
    if not victoria_id:
        logger.warning("Victoria not found, creating...")
        victoria_id = await conn.fetchval("""
            INSERT INTO experts (name, role, system_prompt, department)
            VALUES ('Виктория', 'Team Lead', 'Team Lead and Coordinator', 'Management')
            RETURNING id
        """)
    return victoria_id


async def phase_1_prioritize(conn, *, calculate_task_priority: PriorityFn) -> Dict[str, Any]:
    """Phase 1: Prioritize medium pending tasks from last 24h."""
    t1 = time.time()
    logger.info("📊 Phase 1: Prioritizing existing tasks...")
    unprioritized_tasks = await conn.fetch("""
        SELECT id, title, description, metadata, domain_id
        FROM tasks
        WHERE priority = 'medium'
        AND status = 'pending'
        AND created_at > NOW() - INTERVAL '24 hours'
    """)

    for task in unprioritized_tasks:
        task_meta = (
            json.loads(task["metadata"]) if isinstance(task["metadata"], str) else task["metadata"]
        )
        new_priority = await calculate_task_priority(
            conn, task["title"], task["description"], task_meta, task["domain_id"]
        )
        if new_priority != "medium":
            await conn.execute(
                """
                UPDATE tasks
                SET priority = $1,
                    updated_at = NOW()
                WHERE id = $2
            """,
                new_priority,
                task["id"],
            )
            logger.info("  📌 Task %s: priority updated to %s", task["id"], new_priority)

    duration_ms = (time.time() - t1) * 1000
    logger.info(
        "[ENHANCED_ORCHESTRATOR] phase=1 duration_ms=%.0f result=%s tasks reprioritized",
        duration_ms,
        len(unprioritized_tasks),
    )
    return {"result": len(unprioritized_tasks), "duration_ms": duration_ms}


async def phase_1_5_decompose(
    conn,
    *,
    victoria_id: Any,
    decompose_via_victoria: Callable[[str], Awaitable[Optional[Dict[str, Any]]]],
    assign_task_to_best_expert: AssignFn,
) -> Dict[str, Any]:
    """Phase 1.5: Decompose complex unassigned tasks (Blackboard market + HITL).

    Behavior-preserving extract — including existing control-flow quirks.
    """
    t15 = time.time()
    decomposed_count = 0

    try:
        from agentscope.agents import DialogAgent
        from agentscope.pipelines import SequentialPipeline

        decomposer = DialogAgent(
            name="Decomposer",
            sys_prompt="ТЫ - Архитектор. Разложи задачу на атомарные части (First Principles Thinking).",
            model_config_name="victoria_mlx",
        )
        auditor = DialogAgent(
            name="Auditor",
            sys_prompt="ТЫ - Red Team. Найди 3 причины, почему этот план провалится (Pre-mortem).",
            model_config_name="victoria_mlx",
        )
        _orch_pipeline = SequentialPipeline([decomposer, auditor])  # noqa: F841
    except ImportError:
        _orch_pipeline = None  # noqa: F841

    try:
        complex_unassigned = await conn.fetch("""
            SELECT id, title, description, domain_id, priority, metadata,
                   (metadata->>'project_context') AS project_context
            FROM tasks
            WHERE assignee_expert_id IS NULL
            AND status = 'pending'
            AND (metadata->>'decomposed') IS DISTINCT FROM 'true'
            AND (
                priority IN ('high', 'urgent')
                OR (metadata->>'complex')::boolean = true
            )
            AND parent_task_id IS NULL
            ORDER BY
                CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 ELSE 3 END,
                created_at ASC
            LIMIT 3
        """)
    except Exception as schema_err:
        if "parent_task_id" in str(schema_err).lower() or "column" in str(schema_err).lower():
            logger.debug(
                "Phase 1.5 skipped: parent_task_id not in schema (run add_task_orchestration_schema migration)"
            )
        else:
            logger.warning("Phase 1.5 query failed: %s", schema_err)
        complex_unassigned = []

    for task in complex_unassigned:
        try:
            active_count = await conn.fetchval(
                "SELECT count(*) FROM tasks WHERE status = 'in_progress'"
            )
            if active_count >= 3:
                logger.warning(
                    f"⚠️ [CONCURRENCY GUARD] {active_count} tasks in progress. Skipping decomposition."
                )
                continue

            goal = f"{task['title']}\n\n{task['description'] or ''}"

            try:
                from services.blackboard_service import get_blackboard_service

                blackboard = get_blackboard_service()
                await blackboard.post_goal(
                    str(task["id"]),
                    goal,
                    {
                        "priority": task["priority"],
                        "domain_id": str(task["domain_id"]) if task["domain_id"] else None,
                        "project_context": task.get("project_context"),
                        "is_market_task": True,
                    },
                )
                logger.info(
                    f"🏛️ [MARKET] Goal {task['id']} posted to Blackboard for self-organization."
                )
                continue
            except Exception as market_err:
                logger.warning(f"⚠️ [MARKET] Failed to post to Blackboard: {market_err}")

            struct = await decompose_via_victoria(goal)
            if struct and struct.get("subtasks"):
                subtasks = struct["subtasks"]

                if len(subtasks) >= 3 or (task.get("metadata") or {}).get("complex"):
                    from human_in_the_loop import get_hitl

                    hitl = get_hitl()
                    confidence = struct.get("confidence", 0.0)
                    if confidence >= 0.95:
                        logger.info(
                            f"🚀 [AUTO-IMPL] Высокая уверенность ({confidence:.2f}) для задачи {task['id']}. Авто-одобрение."
                        )
                        await conn.execute(
                            """
                            UPDATE tasks
                            SET metadata = COALESCE(metadata, '{}'::jsonb) || '{"plan_status": "auto_approved", "auto_impl": true}'::jsonb
                            WHERE id = $1
                        """,
                            task["id"],
                        )
                    else:
                        await hitl.request_approval(
                            action="plan_approval",
                            description=f"Одобрение плана для задачи: {task['title']}",
                            agent_name="Виктория",
                            proposed_result=struct,
                            context={
                                "task_id": str(task["id"]),
                                "subtasks_count": len(subtasks),
                            },
                        )
                        if await hitl.check_approval_required("plan_approval"):
                            logger.info(f"⏳ Task {task['id']} is waiting for plan approval.")
                            await conn.execute(
                                """
                                UPDATE tasks
                                SET status = 'pending',
                                    metadata = COALESCE(metadata, '{}'::jsonb) || '{"plan_status": "pending_approval"}'::jsonb
                                WHERE id = $1
                            """,
                                task["id"],
                            )
                            continue

                is_swarm = bool(struct.get("is_swarm", False))

                if struct.get("needs_micro_agent"):
                    try:
                        from expert_generator import recruit_expert

                        micro_domain = struct.get("micro_agent_domain", "General")
                        logger.info(
                            f"🧬 [SPAWNING] Spawning micro-agent for domain: {micro_domain}"
                        )
                        await recruit_expert(micro_domain, is_micro=True)
                    except Exception as se:
                        logger.error(f"❌ [SPAWNING] Failed to spawn micro-agent: {se}")

                if is_swarm:
                    logger.info(f"🐝 [SWARM] Initializing MsgHub for task {task['id']}")
                    try:
                        from agentscope.msghub import msghub  # noqa: F401
                    except ImportError:
                        pass

                for st in subtasks[:5]:  # max 5 subtasks
                    st_desc = st.get("subtask", st.get("description", ""))
                    st_dept = st.get("department", "General")
                    domain_row = await conn.fetchrow(
                        "SELECT id FROM domains WHERE name = $1", st_dept
                    )
                    st_domain_id = domain_row["id"] if domain_row else task["domain_id"]
                    st_contract = st.get("contract")
                    meta = {
                        "source": "orchestrator_decompose",
                        "parent_task_id": str(task["id"]),
                        "expert_role": st.get("expert_role", ""),
                        "is_swarm": is_swarm,
                        "contract": st_contract,
                    }
                    _meta = task.get("metadata")
                    parent_pc = task.get("project_context") or (
                        json.loads(_meta).get("project_context")
                        if isinstance(_meta, str)
                        else (_meta or {}).get("project_context")
                    )
                    # Preserve original post-loop single-insert behavior
                    _priority = st.get("priority", "medium")
                    if isinstance(meta, str):
                        meta_json = json.loads(meta)
                    else:
                        meta_json = meta
                    if meta_json.get("source") == "victoria_monster_delegation":
                        _priority = "low"

                    try:
                        sub_id = await conn.fetchval(
                            """
                            INSERT INTO tasks (title, description, status, priority, domain_id, creator_expert_id, metadata, parent_task_id, project_context)
                            VALUES ($1, $2, 'pending', $3, $4, $5, $6::jsonb, $7, $8)
                            ON CONFLICT (title, COALESCE(project_context, 'default'::character varying))
                            WHERE (status = ANY (ARRAY['pending'::text, 'in_progress'::text]))
                            DO NOTHING
                            RETURNING id
                        """,
                            (st_desc[:255] if len(st_desc) > 255 else st_desc),
                            st_desc,
                            _priority,
                            st_domain_id,
                            victoria_id,
                            json.dumps(meta),
                            task["id"],
                            parent_pc,
                        )
                    except Exception as col_err:
                        if "project_context" in str(col_err) or "column" in str(col_err).lower():
                            sub_id = await conn.fetchval(
                                """
                                INSERT INTO tasks (title, description, status, priority, domain_id, creator_expert_id, metadata, parent_task_id)
                                VALUES ($1, $2, 'pending', $3, $4, $5, $6::jsonb, $7)
                                ON CONFLICT (title, COALESCE(project_context, 'default'::character varying))
                                WHERE (status = ANY (ARRAY['pending'::text, 'in_progress'::text]))
                                DO NOTHING
                                RETURNING id
                            """,
                                (st_desc[:255] if len(st_desc) > 255 else st_desc),
                                st_desc,
                                st.get("priority", "medium"),
                                st_domain_id,
                                victoria_id,
                                meta,
                                task["id"],
                            )
                        else:
                            raise
                    if sub_id:
                        await assign_task_to_best_expert(
                            conn,
                            str(sub_id),
                            st_domain_id,
                            metadata={"assignee_hint": st.get("expert_role")},
                        )
                        decomposed_count += 1
                await conn.execute(
                    """
                    UPDATE tasks
                    SET metadata = COALESCE(metadata, '{}'::jsonb) || '{"decomposed": true}'::jsonb,
                        updated_at = NOW()
                    WHERE id = $1
                """,
                    task["id"],
                )
                logger.info(
                    "  📦 Task %s decomposed into %s subtasks",
                    task["id"],
                    min(len(subtasks), 5),
                )
        except Exception as e:
            logger.warning("Decompose task %s failed: %s", task["id"], e)

    logger.info(
        "[ENHANCED_ORCHESTRATOR] phase=1.5 duration_ms=%.0f result=%s decomposed",
        (time.time() - t15) * 1000,
        decomposed_count,
    )
    return {"decomposed": decomposed_count}


async def phase_1_8_red_team(
    conn, *, run_smart_agent_async: Callable[..., Awaitable[Any]]
) -> Dict[str, Any]:
    """Phase 1.8: Red Team critic audit of decomposed/urgent pending plans."""
    t18 = time.time()
    critique_count = 0
    complex_tasks = await conn.fetch("""
        SELECT id, title, description, metadata
        FROM tasks
        WHERE status = 'pending'
        AND (metadata->>'decomposed' = 'true' OR priority = 'urgent')
        AND (metadata->>'critique_passed') IS NULL
        LIMIT 5
    """)

    for task in complex_tasks:
        try:
            from isolated_context import IsolatedContext

            temp_ctx = IsolatedContext(agent_name="Critic", project_context="Orchestration")
            temp_ctx.add_memory("user", task["description"])
            temp_ctx.prune_context(task["title"], max_chars=2000)

            subtasks = await conn.fetch(
                "SELECT title, description FROM tasks WHERE parent_task_id = $1", task["id"]
            )
            plan_summary = f"Задача: {task['title']}\n"
            plan_summary += "\n".join([f"- {st['title']}" for st in subtasks])

            critic_prompt = f"""Ты - Red Team Critic в корпорации ATRA. Проведи аудит плана.
ПЛАН:
{plan_summary}

Найди:
1. Логические дыры (пропущенные шаги).
2. Риски безопасности или стабильности.
3. Ошибки в зависимостях.

Выдай вердикт: ОДОБРЕНО или КРИТИКА (с описанием правок).
"""
            critic_verdict = await run_smart_agent_async(
                critic_prompt, expert_name="Red Team Critic", category="reasoning"
            )

            is_approved = critic_verdict and "ОДОБРЕНО" in critic_verdict

            if critic_verdict and "КРИТИКА" in critic_verdict:
                logger.warning(
                    f"🚨 [CRITIC] План задачи {task['id']} отклонен: {critic_verdict[:200]}..."
                )
                await conn.execute(
                    """
                    UPDATE tasks
                    SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb,
                        status = 'pending'
                    WHERE id = $1
                """,
                    task["id"],
                    json.dumps({"critique_failed": True, "critic_feedback": critic_verdict}),
                )
            else:
                await conn.execute(
                    """
                    UPDATE tasks
                    SET metadata = COALESCE(metadata, '{}'::jsonb) || '{"critique_passed": true, "ready_for_execution": true}'::jsonb
                    WHERE id = $1
                """,
                    task["id"],
                )
                critique_count += 1
                if is_approved:
                    logger.info(
                        f"✅ [AUTO-IMPL] План задачи {task['id']} прошел аудит и запущен в работу."
                    )
        except Exception as e:
            logger.debug(f"Critic phase failed for task {task['id']}: {e}")

    logger.info(
        "[ENHANCED_ORCHESTRATOR] phase=1.8 duration_ms=%.0f result=%s audited",
        (time.time() - t18) * 1000,
        critique_count,
    )
    return {"audited": critique_count}


async def phase_1_6_batch_group(conn) -> Dict[str, Any]:
    """Phase 1.6: Batch-group small unassigned tasks when enabled."""
    t16 = time.time()
    batch_grouped = 0
    if os.getenv("BATCH_SMALL_TASKS_ENABLED", "").lower() in ("1", "true", "yes"):
        try:
            batch_threshold = int(os.getenv("BATCH_SMALL_TASKS_THRESHOLD", "3"))
            domains_with_many = await conn.fetch(
                """
                SELECT domain_id, COUNT(*) as cnt
                FROM tasks
                WHERE assignee_expert_id IS NULL
                AND status = 'pending'
                AND priority IN ('low', 'medium')
                AND (metadata->>'complex') IS DISTINCT FROM 'true'
                AND domain_id IS NOT NULL
                GROUP BY domain_id
                HAVING COUNT(*) >= $1
            """,
                batch_threshold,
            )
            for row in domains_with_many:
                batch_id = f"batch_{row['domain_id']}"
                await conn.execute(
                    """
                    UPDATE tasks
                    SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb,
                        updated_at = NOW()
                    WHERE assignee_expert_id IS NULL
                    AND status = 'pending'
                    AND domain_id = $1
                    AND priority IN ('low', 'medium')
                    AND (metadata->>'complex') IS DISTINCT FROM 'true'
                """,
                    row["domain_id"],
                    json.dumps({"batch_group": batch_id}),
                )
                batch_grouped += row["cnt"]
        except Exception as e:
            logger.debug("Phase 1.6 (batch grouping) failed: %s", e)

    duration_ms = (time.time() - t16) * 1000
    logger.info(
        "[ENHANCED_ORCHESTRATOR] phase=1.6 duration_ms=%.0f result=%s batch_grouped",
        duration_ms,
        batch_grouped,
    )
    return {"result": batch_grouped, "duration_ms": duration_ms}


async def phase_1_9_execution_optimizer(conn) -> Dict[str, Any]:
    """Phase 1.9: Mark ready_for_execution on pending assigned tasks."""
    t19 = time.time()
    optimized_count = 0
    pending_tasks = await conn.fetch("""
        SELECT id, title, parent_task_id, metadata
        FROM tasks
        WHERE status = 'pending'
        AND assignee_expert_id IS NOT NULL
        AND (metadata->>'critique_passed' = 'true' OR metadata->>'decomposed' IS NULL)
        LIMIT 20
    """)

    if pending_tasks:
        groups: Dict[str, list] = {}
        for t in pending_tasks:
            pid = str(t["parent_task_id"]) if t["parent_task_id"] else "root"
            groups.setdefault(pid, []).append(t)

        for _pid, tasks in groups.items():
            for t in tasks:
                await conn.execute(
                    """
                    UPDATE tasks
                    SET metadata = COALESCE(metadata, '{}'::jsonb) || '{"ready_for_execution": true}'::jsonb
                    WHERE id = $1
                """,
                    t["id"],
                )
                optimized_count += 1

    duration_ms = (time.time() - t19) * 1000
    logger.info(
        "[ENHANCED_ORCHESTRATOR] phase=1.9 duration_ms=%.0f result=%s optimized",
        duration_ms,
        optimized_count,
    )
    return {"result": optimized_count, "duration_ms": duration_ms}


async def phase_2_assign(
    conn,
    *,
    assign_task_to_best_expert: AssignFn,
    record_orch_metric: Optional[Callable[..., None]] = None,
    orch_tasks_assigned=None,
    orch_task_duration=None,
    orch_errors=None,
    orch_tasks_per_phase=None,
) -> Dict[str, Any]:
    """Phase 2: Assign unassigned pending tasks + VIP priority bump."""
    t2 = time.time()
    logger.info("👥 Phase 2: Assigning unassigned tasks...")
    unassigned_tasks = await conn.fetch("""
        SELECT t.id, t.title, t.description, t.domain_id, t.priority, t.metadata
        FROM tasks t
        WHERE t.assignee_expert_id IS NULL
        AND t.status = 'pending'
        AND (t.metadata->>'decomposed') IS DISTINCT FROM 'true'
        ORDER BY
            CASE t.priority
                WHEN 'urgent' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
            END,
            t.created_at ASC
    """)

    assigned_count = 0
    failed_assign_count = 0
    for task in unassigned_tasks:
        task_start = time.time()
        try:
            result = await assign_task_to_best_expert(
                conn, task["id"], task["domain_id"], metadata=task.get("metadata")
            )
            if result:
                assigned_count += 1
                if record_orch_metric:
                    record_orch_metric(
                        "counter", orch_tasks_assigned, phase="phase2", status="success"
                    )
            else:
                failed_assign_count += 1
                if record_orch_metric:
                    record_orch_metric(
                        "counter", orch_tasks_assigned, phase="phase2", status="no_expert"
                    )
        except Exception as assign_err:
            failed_assign_count += 1
            if record_orch_metric:
                record_orch_metric("counter", orch_tasks_assigned, phase="phase2", status="error")
                record_orch_metric("counter", orch_errors, phase="phase2", error_type="assignment")
            logger.debug("Task assignment error: %s", assign_err)
        if record_orch_metric:
            record_orch_metric(
                "histogram", orch_task_duration, "phase2", value=time.time() - task_start
            )
    if record_orch_metric:
        record_orch_metric("counter", orch_tasks_per_phase, "phase2")

    await conn.execute("""
        UPDATE tasks t
        SET priority = 'urgent'
        FROM experts e
        WHERE t.assignee_expert_id = e.id
        AND e.priority = 'VIP'
        AND t.status = 'pending'
        AND t.priority != 'urgent'
    """)

    duration_ms = (time.time() - t2) * 1000
    logger.info(
        "[ENHANCED_ORCHESTRATOR] phase=2 duration_ms=%.0f result=%s assigned, %s failed",
        duration_ms,
        assigned_count,
        failed_assign_count,
    )
    return {
        "assigned": assigned_count,
        "failed": failed_assign_count,
        "duration_ms": duration_ms,
    }


async def phase_3_rebalance(
    conn,
    *,
    rebalance_workload: Callable[..., Awaitable[int]],
    dispatch_pending_assignments: Callable[..., Awaitable[int]],
) -> Dict[str, Any]:
    """Phase 3 + 3.2: Rebalance workload and dispatch if anything moved."""
    t3 = time.time()
    logger.info("⚖️ Phase 3: Rebalancing workload...")
    reassignments = await rebalance_workload(conn)
    logger.info(
        "[ENHANCED_ORCHESTRATOR] phase=3 duration_ms=%.0f result=rebalance reassigned=%s",
        (time.time() - t3) * 1000,
        reassignments,
    )
    dispatched_after_rebalance = 0
    if reassignments > 0:
        t32 = time.time()
        dispatched_after_rebalance = await dispatch_pending_assignments(conn, limit=100)
        logger.info(
            "[ENHANCED_ORCHESTRATOR] phase=3.2 duration_ms=%.0f result=%s dispatched_after_rebalance",
            (time.time() - t32) * 1000,
            dispatched_after_rebalance,
        )
    return {
        "reassignments": reassignments,
        "dispatched": dispatched_after_rebalance,
    }


async def phase_1_95_reconcile(
    conn,
    *,
    reconcile_nonlive_assignments: Callable[..., Awaitable[Tuple[int, int]]],
    reconcile_stale_in_progress: Callable[..., Awaitable[Tuple[int, int]]],
) -> Dict[str, Any]:
    """Phase 1.95: Runtime registry reconcile for non-live / stale tasks."""
    t195 = time.time()
    reopened_pending, reopened_in_progress = await reconcile_nonlive_assignments(conn)
    stale_reopened, stale_fallback_ready = await reconcile_stale_in_progress(conn)
    logger.info(
        "[ENHANCED_ORCHESTRATOR] phase=1.95 duration_ms=%.0f result=%s pending_reopened, %s in_progress_reopened, %s stale_reopened, %s stale_fallback_ready",
        (time.time() - t195) * 1000,
        reopened_pending,
        reopened_in_progress,
        stale_reopened,
        stale_fallback_ready,
    )
    return {
        "reopened_pending": reopened_pending,
        "reopened_in_progress": reopened_in_progress,
        "stale_reopened": stale_reopened,
        "stale_fallback_ready": stale_fallback_ready,
    }


async def phase_1_97_scale_down(
    conn, *, scale_down_idle_dynamic_workers: Callable[..., Awaitable[int]]
) -> Dict[str, Any]:
    """Phase 1.97: Scale down idle dynamic workers."""
    t197 = time.time()
    dynamic_scaled_down = await scale_down_idle_dynamic_workers(conn)
    logger.info(
        "[ENHANCED_ORCHESTRATOR] phase=1.97 duration_ms=%.0f result=%s dynamic_workers_scaled_down",
        (time.time() - t197) * 1000,
        dynamic_scaled_down,
    )
    return {"result": dynamic_scaled_down}


async def phase_2_2_dispatch(
    conn, *, dispatch_pending_assignments: Callable[..., Awaitable[int]], limit: int = 100
) -> Dict[str, Any]:
    """Phase 2.2: Dispatch pending assignments to Redis streams."""
    t22 = time.time()
    dispatched = await dispatch_pending_assignments(conn, limit=limit)
    logger.info(
        "[ENHANCED_ORCHESTRATOR] phase=2.2 duration_ms=%.0f result=%s dispatched_to_stream",
        (time.time() - t22) * 1000,
        dispatched,
    )
    return {"dispatched": dispatched}


async def phase_2_5_rule_fallback(
    conn,
    *,
    rule_executor_can_handle: Callable[[Dict[str, Any]], bool],
    rule_executor_execute: Callable[..., Awaitable[Any]],
) -> Dict[str, Any]:
    """Phase 2.5: Rule-based fallback for stuck / file-check pending tasks."""
    t25 = time.time()
    fallback_for_rd_verify = os.getenv(
        "ORCHESTRATOR_RULE_FALLBACK_FOR_RD_VERIFY", "true"
    ).lower() in (
        "true",
        "1",
        "yes",
    )
    fallback_for_file_audit = os.getenv(
        "ORCHESTRATOR_RULE_FALLBACK_FOR_FILE_AUDIT", "true"
    ).lower() in (
        "true",
        "1",
        "yes",
    )
    fallback_min_attempts = int(os.getenv("ORCHESTRATOR_RULE_FALLBACK_MIN_ATTEMPTS", "3"))
    failed_tasks = await conn.fetch(
        """
        SELECT id, title, description, metadata
        FROM tasks
        WHERE status = 'pending'
        AND (
            COALESCE((metadata->>'attempt_count')::int, 0) >= $2
            OR COALESCE((metadata->>'agent_failed_count')::int, 0) >= $2
            OR (
                $1::boolean = true
                AND COALESCE((metadata->>'stale_force_fallback')::boolean, false) = true
            )
            OR (
                $3::boolean = true
                AND (
                    title ILIKE '%проверь файл%'
                    OR description ILIKE '%проверь файл%'
                    OR title ILIKE '%check file%'
                    OR description ILIKE '%check file%'
                )
            )
        )
        LIMIT 50
    """,
        fallback_for_rd_verify,
        fallback_min_attempts,
        fallback_for_file_audit,
    )
    rule_completed = 0
    for ft in failed_tasks:
        task_dict = dict(ft)
        if isinstance(task_dict.get("metadata"), str):
            try:
                task_dict["metadata"] = json.loads(task_dict["metadata"])
            except Exception:
                task_dict["metadata"] = {}
        if rule_executor_can_handle(task_dict):
            try:
                result = await rule_executor_execute(task_dict)
                if result:
                    from task_rule_executor import finalize_rule_result

                    final_text, meta_patch, db_status = finalize_rule_result(result)
                    meta_patch = {
                        **meta_patch,
                        "orchestrator_fallback": True,
                    }
                    await conn.execute(
                        """
                        UPDATE tasks
                        SET status = $3, result = $2, updated_at = NOW(),
                            metadata = COALESCE(metadata, '{}'::jsonb) || $4::jsonb
                        WHERE id = $1
                    """,
                        ft["id"],
                        final_text,
                        db_status,
                        json.dumps(meta_patch),
                    )
                    if db_status == "completed":
                        rule_completed += 1
                    logger.info(
                        "  rule_executor task %s → %s (degraded=%s)",
                        ft["id"],
                        db_status,
                        meta_patch.get("quality_degraded"),
                    )
            except Exception as e:
                logger.warning("rule_executor failed for task %s: %s", ft["id"], e)
    if failed_tasks:
        logger.info(
            "[ENHANCED_ORCHESTRATOR] phase=2.5 duration_ms=%.0f result=%s rule-based of %s failed",
            (time.time() - t25) * 1000,
            rule_completed,
            len(failed_tasks),
        )
    return {"rule_completed": rule_completed, "candidates": len(failed_tasks)}


async def phase_4_cross_domain(
    conn,
    rd,
    *,
    run_cursor_agent: Callable[..., Awaitable[Any]],
    heavy_phase_step_timeout_sec: int,
    execution_focus: bool,
    has_execution_backlog: Callable[..., Awaitable[bool]],
) -> Dict[str, Any]:
    """Phase 4: Associative brain — cross-domain hypothesis linking.

    Returns interrupted=True when quality-focus backlog appears mid-loop
    (caller must exit the orchestration cycle).
    """
    logger.info("🧩 Phase 4: Cross-domain linking...")
    new_knowledge = await conn.fetch("""
        SELECT k.id, k.content, d.name as domain, k.metadata, k.domain_id
        FROM knowledge_nodes k
        JOIN domains d ON k.domain_id = d.id
        WHERE k.created_at > NOW() - INTERVAL '6 hours'
        AND (k.metadata->>'orchestrated' IS NULL OR k.metadata->>'orchestrated' = 'false')
        LIMIT 10
    """)

    for node in new_knowledge:
        random_node = await conn.fetchrow(
            """
            SELECT k.content, d.name as domain
            FROM knowledge_nodes k JOIN domains d ON k.domain_id = d.id
            WHERE k.domain_id != $1 ORDER BY RANDOM() LIMIT 1
        """,
            node["domain_id"],
        )

        if random_node:
            link_prompt = f"""
                    Вы - Виктория (Team Lead). Найдите неочевидную связь между двумя фактами:
                    ФАКТ А ({node["domain"]}): {node["content"]}
                    ФАКТ Б ({random_node["domain"]}): {random_node["content"]}

                    ЗАДАЧА: Сформулируйте одну инновационную гипотезу на стыке этих знаний.
                    Верните ТОЛЬКО текст гипотезы.
                    """
            try:
                hypothesis = await asyncio.wait_for(
                    run_cursor_agent(link_prompt),
                    timeout=heavy_phase_step_timeout_sec,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "[ENHANCED_ORCHESTRATOR] phase4 step timeout (%ss) for cross-domain hypothesis",
                    heavy_phase_step_timeout_sec,
                )
                hypothesis = None
            if hypothesis:
                content_kn = f"🔬 КРОСС-ДОМЕННАЯ ГИПОТЕЗА: {hypothesis}"
                meta_kn = json.dumps(
                    {"source": "cross_domain_linker", "parents": [str(node["id"])]}
                )
                embedding = None
                try:
                    from semantic_cache import get_embedding

                    embedding = await get_embedding(content_kn[:8000])
                except Exception:
                    pass
                if embedding is not None:
                    kn_id = await conn.fetchval(
                        """
                        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                        VALUES ($1, $2, 0.95, $3, true, $4::vector)
                        RETURNING id
                    """,
                        node["domain_id"],
                        content_kn,
                        meta_kn,
                        str(embedding),
                    )
                else:
                    kn_id = await conn.fetchval(
                        """
                        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                        VALUES ($1, $2, 0.95, $3, true)
                        RETURNING id
                    """,
                        node["domain_id"],
                        content_kn,
                        meta_kn,
                    )
                if rd:
                    await rd.xadd(
                        "knowledge_stream",
                        {"type": "synthetic_link", "content": hypothesis},
                    )
                try:
                    from nightly_learner import create_debate_for_hypothesis

                    await create_debate_for_hypothesis(
                        conn,
                        kn_id,
                        f"🔬 КРОСС-ДОМЕННАЯ ГИПОТЕЗА: {hypothesis}",
                        node["domain_id"],
                    )
                except Exception as db_err:
                    logger.debug("Hypothesis debate skip: %s", db_err)

        await conn.execute(
            """
            UPDATE knowledge_nodes
            SET metadata = metadata || '{"orchestrated": "true"}'::jsonb
            WHERE id = $1
        """,
            node["id"],
        )
        if execution_focus and await has_execution_backlog(conn):
            logger.info(
                "[ENHANCED_ORCHESTRATOR] quality-focus: backlog appeared during phase4, interrupt heavy phases"
            )
            return {"interrupted": True, "nodes": len(new_knowledge)}

    return {"interrupted": False, "nodes": len(new_knowledge)}


async def phase_5_curiosity(
    conn,
    *,
    victoria_id: Any,
    get_ollama_latency: Callable[[], Awaitable[float]],
    canonical_domain: Callable[[str], str],
    justify_task_value: Callable[..., Awaitable[Tuple[bool, str]]],
    get_best_expert_for_domain: Callable[..., Awaitable[Any]],
    same_task_for_expert_in_last_n_days: Optional[Callable[..., Awaitable[bool]]],
    assign_task_to_best_expert: AssignFn,
    dispatch_pending_assignments: Callable[..., Awaitable[int]],
    execution_focus: bool,
    has_execution_backlog: Callable[..., Awaitable[bool]],
    expert_generator_path: str,
) -> Dict[str, Any]:
    """Phase 5: Curiosity Engine (deserts → research tasks) + quality-focus exits.

    Returns:
      interrupted=True  → backlog mid-phase5, caller must exit cycle
      finish_cycle=True → execution_focus: skip scout/6–8/heavy_tail
    """
    logger.info("🔍 Phase 5: Curiosity Engine...")

    ollama_latency = await get_ollama_latency()
    if ollama_latency > 1.0:
        logger.warning(
            "⏸️ RESOURCE-DRIVEN CURIOSITY: Ollama latency high (%.2fs > 1.0s). Curiosity Engine sleeps.",
            ollama_latency,
        )
        deserts = []
    else:
        pending_count = await conn.fetchval("SELECT count(*) FROM tasks WHERE status = 'pending'")
        max_pending = int(os.getenv("SMART_WORKER_MAX_PENDING", "5"))

        try:
            import psutil

            mem = psutil.virtual_memory()
            if mem.percent > 85:
                logger.warning(
                    f"🚨 [HEALTH-AWARE] RAM usage high ({mem.percent}%). Reducing max_pending to 1."
                )
                max_pending = 1
            elif mem.percent > 70:
                logger.warning(
                    f"⚠️ [HEALTH-AWARE] RAM usage moderate ({mem.percent}%). Reducing max_pending to 3."
                )
                max_pending = 3
        except ImportError:
            pass

        if pending_count >= max_pending:
            logger.warning(
                "⏸️ BACKPRESSURE: Too many pending tasks (%s/%s). Skipping Curiosity Engine research tasks.",
                pending_count,
                max_pending,
            )
            deserts = []
        else:
            deserts = await conn.fetch("""
                SELECT d.id, d.name, count(k.id) as node_count
                FROM domains d LEFT JOIN knowledge_nodes k ON d.id = k.domain_id
                GROUP BY d.id, d.name
                HAVING count(k.id) < 50 OR max(k.created_at) < NOW() - INTERVAL '48 hours'
                ORDER BY count(k.id) ASC
                LIMIT 5
            """)

    curiosity_min_completed_10m = int(os.getenv("ORCHESTRATOR_CURIOSITY_MIN_COMPLETED_10M", "1"))
    completed_10m_now = await conn.fetchval(
        """
        SELECT count(*)
        FROM tasks
        WHERE status = 'completed'
          AND updated_at > NOW() - INTERVAL '10 minutes'
        """
    )
    if int(completed_10m_now or 0) < curiosity_min_completed_10m:
        logger.info(
            "⏸️ CURIOSITY THROTTLE: completed_10m=%s < min=%s, skip curiosity creation this cycle",
            completed_10m_now,
            curiosity_min_completed_10m,
        )
        deserts = []

    autonomous_count = await conn.fetchval(
        "SELECT count(*) FROM experts WHERE (metadata->>'is_autonomous')::text = 'true'"
    )
    autonomous_limit = int(os.getenv("AUTONOMOUS_EXPERT_LIMIT", "25"))
    max_active_curiosity = int(os.getenv("ORCHESTRATOR_MAX_ACTIVE_CURIOSITY_TASKS", "1"))

    curiosity_assigned = 0
    curiosity_cooldown_min = int(os.getenv("ORCHESTRATOR_CURIOSITY_RETRY_COOLDOWN_MIN", "30"))
    global_curiosity_cb = await conn.fetchval(
        """
        SELECT 1
        FROM tasks
        WHERE COALESCE(metadata->>'reason', '') = 'curiosity_engine_starvation'
          AND status IN ('failed', 'cancelled')
          AND updated_at > NOW() - ($1::text || ' minutes')::interval
          AND (
              COALESCE(metadata->>'auto_fallback_reason', '') = 'circuit_breaker_loop_exhausted'
              OR COALESCE(metadata->>'last_error', '') ILIKE '%Circuit Breaker%'
              OR COALESCE(result, '') ILIKE '%Circuit Breaker%'
          )
        LIMIT 1
        """,
        str(curiosity_cooldown_min),
    )
    if global_curiosity_cb:
        logger.info(
            "  ⏭️ Curiosity global cooldown: recent Circuit Breaker on starvation tasks within %s min",
            curiosity_cooldown_min,
        )
        deserts = []

    for desert in deserts:
        active_curiosity = await conn.fetchval(
            """
            SELECT count(*)
            FROM tasks
            WHERE status IN ('pending', 'in_progress')
              AND COALESCE(metadata->>'reason', '') = 'curiosity_engine_starvation'
            """
        )
        if int(active_curiosity or 0) >= max_active_curiosity:
            logger.info(
                "  ⏭️ Curiosity budget reached: active=%s limit=%s",
                active_curiosity,
                max_active_curiosity,
            )
            continue
        canonical = canonical_domain(desert["name"])
        expert_count = await conn.fetchval(
            "SELECT count(*) FROM experts WHERE department = $1 OR department = $2",
            desert["name"],
            canonical,
        )
        if expert_count == 0 and (autonomous_count or 0) < autonomous_limit:
            logger.info(
                "  🔍 Recruiting expert for %s (canonical: %s)...",
                desert["name"],
                canonical,
            )
            subprocess.run(["python3", expert_generator_path, canonical], check=False)
            autonomous_count = (autonomous_count or 0) + 1

        curiosity_task = (
            f"Проведи глубокое исследование новых технологий и трендов 2026 "
            f"в области {desert['name']}. Найди 3 прорывных инсайта."
        )
        title_curiosity = f"🔥 ИССЛЕДОВАНИЕ: {desert['name']}"

        is_valuable, reason = await justify_task_value(title_curiosity, curiosity_task)
        if not is_valuable:
            logger.info(
                "  ⏭️ Skip Curiosity task for %s: low value (reason: %s)",
                desert["name"],
                reason,
            )
            continue

        best_expert = await get_best_expert_for_domain(conn, desert["id"])
        if best_expert and same_task_for_expert_in_last_n_days:
            if await same_task_for_expert_in_last_n_days(
                conn, title_curiosity, curiosity_task, best_expert["id"], days=30
            ):
                logger.info(
                    "  ⏭️ Skip duplicate: same research task for expert %s (%s) in last 30 days",
                    best_expert.get("name"),
                    desert["name"],
                )
                continue
        curiosity_cooldown_min = int(os.getenv("ORCHESTRATOR_CURIOSITY_RETRY_COOLDOWN_MIN", "30"))
        # Cooldown is per title (any expert): CB timeout used to cancel, not fail,
        # and a new assignee (Инна vs Роман) bypassed same_task_for_expert.
        recent_curiosity_failure = await conn.fetchval(
            """
            SELECT 1
            FROM tasks
            WHERE title = $1
              AND status IN ('failed', 'cancelled')
              AND updated_at > NOW() - ($2::text || ' minutes')::interval
              AND (
                  COALESCE(metadata->>'auto_fallback_reason', '') IN (
                      'curiosity_no_llm_progress_timeout',
                      'pending_curiosity_starvation_timeout',
                      'circuit_breaker_loop_exhausted'
                  )
                  OR COALESCE(metadata->>'last_error', '') ILIKE '%Circuit Breaker%'
                  OR COALESCE(result, '') ILIKE '%Circuit Breaker%'
              )
            LIMIT 1
            """,
            title_curiosity,
            str(curiosity_cooldown_min),
        )
        if recent_curiosity_failure:
            logger.info(
                "  ⏭️ Curiosity cooldown active for %s (recent timeout fallback within %s min)",
                desert["name"],
                curiosity_cooldown_min,
            )
            continue
        priority = "high" if desert["node_count"] < 20 else "medium"
        try:
            task_id = await conn.fetchval(
                """
                INSERT INTO tasks (title, description, status, priority, creator_expert_id, domain_id, metadata)
                VALUES ($1, $2, 'pending', $3, $4, $5, $6)
                ON CONFLICT (title, COALESCE(project_context, 'default'::character varying))
                WHERE (status = ANY (ARRAY['pending'::text, 'in_progress'::text]))
                DO UPDATE SET updated_at = NOW()
                RETURNING id
            """,
                title_curiosity,
                curiosity_task,
                priority,
                victoria_id,
                desert["id"],
                json.dumps(
                    {
                        "reason": "curiosity_engine_starvation",
                        "node_count": desert["node_count"],
                        "justification": reason,
                        "is_autonomous": True,
                    }
                ),
            )
            if task_id:
                await assign_task_to_best_expert(conn, task_id, desert["id"])
                curiosity_assigned += 1
        except Exception as task_err:
            if "duplicate" in str(task_err).lower() or "23505" in str(task_err):
                logger.info(f"  ⏭️ Task already exists (dedup): {title_curiosity[:50]}")
            else:
                raise
    if curiosity_assigned > 0:
        t52 = time.time()
        dispatched_curiosity = await dispatch_pending_assignments(conn, limit=100)
        logger.info(
            "[ENHANCED_ORCHESTRATOR] phase=5.2 duration_ms=%.0f result=%s dispatched_curiosity",
            (time.time() - t52) * 1000,
            dispatched_curiosity,
        )
    if execution_focus and await has_execution_backlog(conn):
        logger.info(
            "[ENHANCED_ORCHESTRATOR] quality-focus: backlog appeared during phase5, interrupt heavy phases"
        )
        return {
            "curiosity_assigned": curiosity_assigned,
            "interrupted": True,
            "finish_cycle": False,
        }
    if execution_focus:
        logger.info(
            "[ENHANCED_ORCHESTRATOR] quality-focus: finish live cycle after phase5 (heavy phases delegated to nightly)"
        )
        return {
            "curiosity_assigned": curiosity_assigned,
            "interrupted": False,
            "finish_cycle": True,
        }
    return {
        "curiosity_assigned": curiosity_assigned,
        "interrupted": False,
        "finish_cycle": False,
    }


async def phase_5_8_rnd(
    conn,
    *,
    victoria_id: Any,
    heavy_phase_step_timeout_sec: int,
    run_global_scout_cycle: Callable[[], Awaitable[Any]],
    run_auto_link_detection: Callable[[], Awaitable[Any]],
    get_distiller: Callable[[], Any],
    get_synthetic_generator: Callable[[], Any],
    get_training_pipeline: Callable[[], Any],
) -> Dict[str, Any]:
    """Phases 5(scout)+6+7+8: Global Scout, auto-link, distill, self-repair."""
    logger.info("🌐 Phase 5: Running Global Scout validation...")
    try:
        await asyncio.wait_for(
            run_global_scout_cycle(),
            timeout=heavy_phase_step_timeout_sec,
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Global Scout error: %s", exc)

    logger.info("🔗 Phase 6: Running auto-link detection...")
    try:
        await asyncio.wait_for(
            run_auto_link_detection(),
            timeout=heavy_phase_step_timeout_sec,
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Auto-link detection error: %s", exc)

    logger.info("🧬 Phase 7: Knowledge Distillation & Auto-Upgrade...")
    try:
        distiller = get_distiller()
        distilled_count = await asyncio.wait_for(
            distiller.collect_high_quality_samples(days=1),
            timeout=heavy_phase_step_timeout_sec,
        )
        if distilled_count > 0:
            logger.info("  ✨ Distilled %d high-quality samples.", distilled_count)
        generator = get_synthetic_generator()
        await asyncio.wait_for(
            generator.generate_synthetic_samples(limit=5),
            timeout=heavy_phase_step_timeout_sec,
        )
        pipeline = get_training_pipeline()
        status = pipeline.trigger_auto_upgrade()
        if "ЗАПУЩЕН" in status or "ГОТОВ" in status:
            logger.info("  🔥 AUTONOMOUS UPGRADE STATUS: %s", status)
            await conn.execute("INSERT INTO notifications (message) VALUES ($1)", status)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Distillation error: %s", exc)

    logger.info("🔧 Phase 8: Self-Repair Engine...")
    repair_created = 0
    try:
        errors = await conn.fetch("""
            SELECT id, user_query, assistant_response, metadata
            FROM interaction_logs
            WHERE (assistant_response LIKE '❌%' OR assistant_response LIKE '⚠️%')
            AND created_at > NOW() - INTERVAL '1 hour'
            AND (metadata->>'repaired' IS NULL OR metadata->>'repaired' = 'false')
            LIMIT 5
        """)
        for err in errors:
            repair_task = (
                f"ОШИБКА В СИСТЕМЕ: {err['assistant_response']}\n"
                f"ЗАПРОС: {err['user_query']}\n\n"
                f"ЗАДАЧА: Проанализируй логи и код, найди причину и предложи исправление."
            )
            await conn.execute(
                """
                INSERT INTO tasks (title, description, status, priority, creator_expert_id, metadata)
                VALUES ($1, $2, 'pending', 'urgent', $3, $4)
                ON CONFLICT (title, COALESCE(project_context, 'default'::character varying))
                WHERE (status = ANY (ARRAY['pending'::text, 'in_progress'::text]))
                DO UPDATE SET updated_at = NOW()
            """,
                "🚨 АВТО-РЕМОНТ: Ошибка",
                repair_task,
                victoria_id,
                json.dumps({"source": "self_repair", "log_id": str(err["id"])}),
            )
            await conn.execute(
                """
                UPDATE interaction_logs
                SET metadata = metadata || '{"repaired": "true"}'::jsonb
                WHERE id = $1
            """,
                err["id"],
            )
            repair_created += 1
            logger.info("  🔧 Created repair task for log %s", err["id"])
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Self-repair error: %s", exc)

    return {"repair_created": repair_created}


async def phase_heavy_tail(
    conn,
    rd,
    *,
    get_swarm_orchestrator: Callable[[], Any],
    get_meta_architect: Callable[[], Any],
    get_evolution_monitor: Callable[[], Any],
    get_curiosity_engine: Callable[[], Any],
    get_memory_consolidator: Callable[[], Any],
    get_multi_cluster_bridge: Callable[[], Any],
    get_server_knowledge_sync: Callable[[], Any],
    get_knowledge_archiver: Callable[[], Any],
    multi_cluster_bridge_cls: Any = None,
    server_knowledge_sync_cls: Any = None,
) -> None:
    """Phases 10–16: thin wrappers around autonomous subsystems (behavior preserved)."""
    logger.info("🐝 Phase 10: Swarm War-Room...")
    try:
        swarm = get_swarm_orchestrator()
        await swarm.handle_critical_failures()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Swarm error: %s", exc)

    logger.info("🏗️ Phase 11: Meta-Architect Review...")
    try:
        architect = get_meta_architect()
        await architect.self_repair_cycle()
        # Cautious code-mutation path (cooldown + max 1 hotspot by default)
        if hasattr(architect, "run_guarded_evolution"):
            evo_status = await architect.run_guarded_evolution()
            logger.info("🏗️ Phase 11 evolution: %s", evo_status)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Meta-Architect error: %s", exc)

    logger.info("🧬 Phase 12: Autonomous Evolution...")
    try:
        evolution = get_evolution_monitor()
        evolution_report = await evolution.run_daily_check()
        logger.info("  %s", evolution_report)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Evolution error: %s", exc)

    logger.info("🔍 Phase 13: Curiosity Engine Gap Analysis...")
    try:
        curiosity = get_curiosity_engine()
        gap_result = await curiosity.scan_for_gaps()
        logger.info("  %s", gap_result)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Curiosity error: %s", exc)

    logger.info("🧠 Phase 14: Memory Consolidation (The Dreaming)...")
    try:
        consolidator = get_memory_consolidator()
        consolidation_result = await consolidator.consolidate_memory()
        logger.info("  %s", consolidation_result)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Consolidation error: %s", exc)

    logger.info("🌐 Phase 14.5: Multi-Cluster Bridge Sync...")
    if multi_cluster_bridge_cls:
        try:
            bridge = get_multi_cluster_bridge()
            if bridge is None:
                raise RuntimeError("MultiClusterBridge unavailable")
            await bridge.initialize(conn)
            await bridge.send_heartbeat()
            await bridge.gossip_sync()
            await bridge.task_tunneling()
            logger.info("  ✅ Multi-cluster sync completed.")
        except Exception as exc:
            logger.error("Multi-cluster bridge error: %s", exc)

    logger.info("🌐 Phase 15: Global Team Knowledge Sync...")
    if server_knowledge_sync_cls:
        try:
            last_sync_key = "last_global_sync"
            last_sync = None
            if rd:
                last_sync = await rd.get(last_sync_key)
            now_str = datetime.now().isoformat()
            should_sync = True
            if last_sync:
                last_sync_dt = datetime.fromisoformat(last_sync)
                if datetime.now() - last_sync_dt < timedelta(hours=1):
                    should_sync = False
            if should_sync:
                sync_manager = get_server_knowledge_sync()
                if sync_manager is None:
                    raise RuntimeError("ServerKnowledgeSync unavailable")
                await sync_manager.sync_experts()
                synced_count = await sync_manager.sync_reports(limit=50)
                logger.info("  📥 Synced %d reports and full team hierarchy.", synced_count)
                if rd:
                    await rd.set(last_sync_key, now_str)
            else:
                logger.info("  ⏭️ Sync skipped (already synced recently).")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Sync error: %s", exc)
    else:
        logger.info("  ⚠️ ServerKnowledgeSync module not found.")

    logger.info("📦 Phase 16: Knowledge Archivation...")
    try:
        archiver = get_knowledge_archiver()
        archive_key = "last_knowledge_archive"
        last_archive = None
        if rd:
            last_archive = await rd.get(archive_key)
        now_str = datetime.now().isoformat()
        should_archive = True
        if last_archive:
            last_archive_dt = datetime.fromisoformat(last_archive)
            if datetime.now() - last_archive_dt < timedelta(days=1):
                should_archive = False
        if should_archive:
            await archiver.periodic_archive_task()
            if rd:
                await rd.set(archive_key, now_str)
            logger.info("  ✅ Knowledge archivation completed.")
        else:
            logger.info("  ⏭️ Archive skipped (already archived today).")
    except ImportError:
        logger.info("  ⚠️ KnowledgeArchiver module not found.")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Archive error: %s", exc)
