"""
State Checkpoint Manager — Agent state save/restore/rollback.
Saves agent state (tasks, memory, sessions, full snapshots) to PostgreSQL.
Provides checkpoint chains for rollback and full-state bundling.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import asyncpg

    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.debug("asyncpg not available, state checkpoints will be disabled")

try:
    from app.db_pool import get_pool
except ImportError:
    try:
        from db_pool import get_pool
    except ImportError:
        get_pool = None


@dataclass
class Checkpoint:
    checkpoint_id: str
    agent_name: str
    timestamp: datetime
    state_type: str
    state_data: Dict[str, Any]
    parent_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)


class StateCheckpointManager:
    def __init__(self):
        self._pool = None

    async def _get_pool(self):
        if self._pool is not None:
            return self._pool
        if get_pool is not None:
            try:
                return await get_pool()
            except Exception as exc:
                logger.debug("state_checkpoint falling back to local pool: %s", exc)
        import os

        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql://admin:secret@localhost:6432/knowledge_os",
        )
        self._pool = await asyncpg.create_pool(
            db_url,
            min_size=1,
            max_size=5,
            command_timeout=30,
            max_inactive_connection_lifetime=300,
        )
        return self._pool

    async def _init_table(self):
        if not DB_AVAILABLE:
            return
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_checkpoints (
                    id VARCHAR(64) PRIMARY KEY,
                    agent_name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    state_type VARCHAR(50) NOT NULL,
                    state_data JSONB NOT NULL,
                    parent_id VARCHAR(64),
                    tags JSONB DEFAULT '[]'
                );
                CREATE INDEX IF NOT EXISTS idx_ac_agent ON agent_checkpoints(agent_name);
                CREATE INDEX IF NOT EXISTS idx_ac_created ON agent_checkpoints(created_at);
                CREATE INDEX IF NOT EXISTS idx_ac_type ON agent_checkpoints(state_type);
            """)

    async def save(
        self,
        agent_name: str,
        state_type: str,
        state_data: Dict[str, Any],
        tags: Optional[List[str]] = None,
        parent_id: Optional[str] = None,
    ) -> str:
        if not DB_AVAILABLE:
            return ""
        pool = await self._get_pool()
        checkpoint_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)
        tags_json = json.dumps(tags or [])
        data_json = json.dumps(state_data, default=str)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_checkpoints (id, agent_name, created_at, state_type, state_data, parent_id, tags)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                checkpoint_id,
                agent_name,
                now,
                state_type,
                data_json,
                parent_id,
                tags_json,
            )
        logger.info("checkpoint %s saved for %s (type=%s)", checkpoint_id, agent_name, state_type)
        return checkpoint_id

    async def save_task_state(
        self,
        task_id: str,
        agent_name: str,
        task_data: Dict[str, Any],
        result: Any,
    ) -> str:
        state_data = {
            "task_id": task_id,
            "task_data": task_data,
            "result": result,
        }
        return await self.save(
            agent_name=agent_name,
            state_type="task",
            state_data=state_data,
            tags=["task", agent_name.lower()],
        )

    async def save_session_state(
        self,
        session_id: str,
        agent_name: str,
        messages: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> str:
        state_data = {
            "session_id": session_id,
            "messages": messages,
            "context": context,
        }
        return await self.save(
            agent_name=agent_name,
            state_type="session",
            state_data=state_data,
            tags=["session", agent_name.lower()],
        )

    async def save_full_state(self, agent_name: str) -> str:
        pool = await self._get_pool()
        state_data: Dict[str, Any] = {"agent_name": agent_name, "snapshot": {}}

        async with pool.acquire() as conn:
            active_tasks = await conn.fetch(
                "SELECT id, title, status, priority, metadata "
                "FROM tasks WHERE status IN ('pending', 'in_progress') "
                "AND (metadata->>'assigned_agent' = $1 OR metadata->>'assigned_agent' IS NULL) "
                "ORDER BY created_at DESC LIMIT 50",
                agent_name,
            )
            state_data["snapshot"]["active_tasks"] = [
                dict(r) for r in active_tasks
            ]

            crystals = await conn.fetch(
                "SELECT project_context, crystal_type, content, confidence_score, metadata "
                "FROM memory_crystals ORDER BY created_at DESC LIMIT 50",
            )
            state_data["snapshot"]["memory_crystals"] = [
                dict(r) for r in crystals
            ]

            try:
                episodes = await conn.fetch(
                    "SELECT user_key, project_context, episode_type, content, metadata "
                    "FROM episodic_memory ORDER BY updated_at DESC LIMIT 50",
                )
                state_data["snapshot"]["episodic_memory"] = [dict(r) for r in episodes]
            except Exception:
                state_data["snapshot"]["episodic_memory"] = []

            decisions = await conn.fetch(
                "SELECT id, question, directive_text, structured_decision, created_at "
                "FROM board_decisions ORDER BY created_at DESC LIMIT 10",
            )
            state_data["snapshot"]["board_decisions"] = [dict(r) for r in decisions]

            goals = await conn.fetch(
                "SELECT id, goal, status, created_at FROM agent_goals "
                "WHERE agent_name = $1 AND status = 'in_progress' "
                "ORDER BY created_at DESC LIMIT 20",
                agent_name,
            )
            state_data["snapshot"]["active_goals"] = [dict(r) for r in goals]

        return await self.save(
            agent_name=agent_name,
            state_type="full",
            state_data=state_data,
            tags=["full", agent_name.lower(), "snapshot"],
        )

    async def get(self, checkpoint_id: str) -> Optional[Checkpoint]:
        if not DB_AVAILABLE:
            return None
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, agent_name, created_at, state_type, state_data, parent_id, tags "
                "FROM agent_checkpoints WHERE id = $1",
                checkpoint_id,
            )
            if row is None:
                return None
            return Checkpoint(
                checkpoint_id=row["id"],
                agent_name=row["agent_name"],
                timestamp=row["created_at"],
                state_type=row["state_type"],
                state_data=json.loads(row["state_data"]),
                parent_id=row["parent_id"],
                tags=json.loads(row["tags"]) if row.get("tags") else [],
            )

    async def get_latest(
        self, agent_name: str, state_type: Optional[str] = None
    ) -> Optional[Checkpoint]:
        if not DB_AVAILABLE:
            return None
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if state_type:
                row = await conn.fetchrow(
                    "SELECT id, agent_name, created_at, state_type, state_data, parent_id, tags "
                    "FROM agent_checkpoints WHERE agent_name = $1 AND state_type = $2 "
                    "ORDER BY created_at DESC LIMIT 1",
                    agent_name,
                    state_type,
                )
            else:
                row = await conn.fetchrow(
                    "SELECT id, agent_name, created_at, state_type, state_data, parent_id, tags "
                    "FROM agent_checkpoints WHERE agent_name = $1 "
                    "ORDER BY created_at DESC LIMIT 1",
                    agent_name,
                )
            if row is None:
                return None
            return Checkpoint(
                checkpoint_id=row["id"],
                agent_name=row["agent_name"],
                timestamp=row["created_at"],
                state_type=row["state_type"],
                state_data=json.loads(row["state_data"]),
                parent_id=row["parent_id"],
                tags=json.loads(row["tags"]) if row.get("tags") else [],
            )

    async def list_checkpoints(
        self,
        agent_name: str,
        limit: int = 10,
        state_type: Optional[str] = None,
    ) -> List[Checkpoint]:
        if not DB_AVAILABLE:
            return []
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if state_type:
                rows = await conn.fetch(
                    "SELECT id, agent_name, created_at, state_type, state_data, parent_id, tags "
                    "FROM agent_checkpoints WHERE agent_name = $1 AND state_type = $2 "
                    "ORDER BY created_at DESC LIMIT $3",
                    agent_name,
                    state_type,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    "SELECT id, agent_name, created_at, state_type, state_data, parent_id, tags "
                    "FROM agent_checkpoints WHERE agent_name = $1 "
                    "ORDER BY created_at DESC LIMIT $2",
                    agent_name,
                    limit,
                )
            return [
                Checkpoint(
                    checkpoint_id=r["id"],
                    agent_name=r["agent_name"],
                    timestamp=r["created_at"],
                    state_type=r["state_type"],
                    state_data=json.loads(r["state_data"]),
                    parent_id=r["parent_id"],
                    tags=json.loads(r["tags"]) if r.get("tags") else [],
                )
                for r in rows
            ]

    async def restore_task(self, checkpoint_id: str):
        cp = await self.get(checkpoint_id)
        if cp is None:
            return False, f"checkpoint {checkpoint_id} not found"
        if cp.state_type not in ("task", "full"):
            return False, f"checkpoint type '{cp.state_type}' is not a task checkpoint"

        if cp.state_type == "task":
            task_data = cp.state_data.get("task_data", {})
            task_id = cp.state_data.get("task_id")
            result = cp.state_data.get("result")
        else:
            tasks_snapshot = cp.state_data.get("snapshot", {}).get("active_tasks", [])
            if not tasks_snapshot:
                return False, "full checkpoint has no task data to restore"
            task_entry = tasks_snapshot[0]
            task_data = {
                "title": task_entry.get("title"),
                "status": task_entry.get("status", "pending"),
                "priority": task_entry.get("priority", "medium"),
                "metadata": task_entry.get("metadata", {}),
            }
            task_id = task_entry.get("id")
            result = None

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if task_id:
                await conn.execute(
                    """
                    UPDATE tasks SET
                        status = $2,
                        metadata = metadata || $3::jsonb,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    task_id,
                    task_data.get("status", "pending"),
                    json.dumps(task_data.get("metadata", {})),
                )
            else:
                task_id = await conn.fetchval(
                    """
                    INSERT INTO tasks (title, description, status, priority, metadata)
                    VALUES ($1, $2, $3, $4, $5::jsonb)
                    RETURNING id
                    """,
                    task_data.get("title", "restored task"),
                    task_data.get("description", ""),
                    task_data.get("status", "pending"),
                    task_data.get("priority", "medium"),
                    json.dumps(task_data.get("metadata", {})),
                )

        try:
            from app.redis_manager import redis_manager

            await redis_manager.release_task_lock(str(task_id) if task_id else "")
        except ImportError:
            try:
                from redis_manager import redis_manager

                await redis_manager.release_task_lock(str(task_id) if task_id else "")
            except Exception as exc:
                logger.debug("redis lock release skipped: %s", exc)

        return True, f"task {task_id} restored from checkpoint {checkpoint_id}"

    async def rollback(self, agent_name: str, steps: int = 1):
        if steps < 1:
            return False, "steps must be >= 1"
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, state_type, state_data, created_at "
                "FROM agent_checkpoints WHERE agent_name = $1 "
                "ORDER BY created_at DESC LIMIT $2",
                agent_name,
                steps,
            )
            if len(rows) < steps:
                return (
                    False,
                    f"only {len(rows)} checkpoints found for {agent_name}, need {steps}",
                )

            target = rows[steps - 1]
            cp_id = target["id"]
            state_type = target["state_type"]
            state_data = json.loads(target["state_data"])

            rollback_cp_id = await self.save(
                agent_name=agent_name,
                state_type="rollback_safety",
                state_data={
                    "rolled_back_to": cp_id,
                    "rollback_of_type": state_type,
                    "previous_state": state_data,
                },
                tags=["rollback", agent_name.lower(), "safety"],
            )
            logger.info(
                "rollback safety checkpoint %s created before rolling back %s to %s",
                rollback_cp_id,
                agent_name,
                cp_id,
            )

            if state_type == "task":
                ok, msg = await self.restore_task(cp_id)
                if not ok:
                    return False, msg
            elif state_type == "full":
                snapshot = state_data.get("snapshot", {})
                active_tasks = snapshot.get("active_tasks", [])
                for task_entry in active_tasks:
                    t_id = task_entry.get("id")
                    t_status = task_entry.get("status", "pending")
                    t_metadata = task_entry.get("metadata", {})
                    if t_id:
                        await conn.execute(
                            """
                            UPDATE tasks SET status = $2, metadata = metadata || $3::jsonb, updated_at = NOW()
                            WHERE id = $1
                            """,
                            t_id,
                            t_status,
                            json.dumps(t_metadata),
                        )
                return True, f"rolled back {agent_name} to full snapshot checkpoint {cp_id}"
            else:
                return True, f"rollback to {state_type} checkpoint {cp_id} recorded (no direct action)"

        return True, f"agent {agent_name} rolled back {steps} step(s) to checkpoint"

    async def cleanup(self, agent_name: str, keep_last: int = 50):
        if not DB_AVAILABLE:
            return
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM agent_checkpoints
                WHERE agent_name = $1
                  AND id NOT IN (
                      SELECT id FROM agent_checkpoints
                      WHERE agent_name = $1
                      ORDER BY created_at DESC
                      LIMIT $2
                  )
                """,
                agent_name,
                keep_last,
            )
            count = result.split()[-1] if " " in result else "0"
            logger.info("cleanup for %s: removed %s checkpoints (keeping %d)", agent_name, count, keep_last)

    async def cleanup_all(self, keep_last: int = 50):
        if not DB_AVAILABLE:
            return
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            agents = await conn.fetch(
                "SELECT DISTINCT agent_name FROM agent_checkpoints"
            )
            for row in agents:
                agent = row["agent_name"]
                await self.cleanup(agent, keep_last=keep_last)


_instance: Optional[StateCheckpointManager] = None


def get_state_checkpoint_manager() -> StateCheckpointManager:
    global _instance
    if _instance is None:
        _instance = StateCheckpointManager()
    return _instance
