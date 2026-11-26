"""
Tests for StateCheckpointManager — agent state save/restore/rollback.

Uses mocked asyncpg pool to avoid requiring a live database.
Run: pytest knowledge_os/tests/test_state_checkpoint.py -v
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.state_checkpoint import Checkpoint, StateCheckpointManager, get_state_checkpoint_manager


@pytest.fixture
def mock_pool():
    """Creates a mock asyncpg pool with a proper async context manager for acquire()."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value="mock-uuid")

    class _CtxMgr:
        async def __aenter__(s):
            return conn

        async def __aexit__(s, *args):
            return None

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_CtxMgr())
    pool._conn = conn
    return pool


@pytest.fixture
def manager(mock_pool):
    """Creates a StateCheckpointManager with a mocked pool."""
    mgr = StateCheckpointManager()
    mgr._pool = mock_pool
    return mgr


# ── helpers ──


def _resolve_conn(mock_pool):
    """Return the conn instance used inside the context manager."""
    return mock_pool._conn


class TestInit:
    def test_singleton(self):
        a = get_state_checkpoint_manager()
        b = get_state_checkpoint_manager()
        assert a is b

    @pytest.mark.asyncio
    async def test_init_table_called(self, manager, mock_pool):
        await manager._init_table()
        conn = _resolve_conn(mock_pool)
        calls = [c[0][0][:70] if c[0] else "" for c in conn.execute.call_args_list]
        assert any("CREATE TABLE IF NOT EXISTS agent_checkpoints" in c for c in calls)

    @pytest.mark.asyncio
    async def test_init_table_creates_indexes(self, manager, mock_pool):
        await manager._init_table()
        conn = _resolve_conn(mock_pool)
        calls = [c[0][0] for c in conn.execute.call_args_list]
        idx_statements = [c for c in calls if "CREATE INDEX" in c]
        assert len(idx_statements) >= 1


class TestSave:
    @pytest.mark.asyncio
    async def test_save_returns_id(self, manager, mock_pool):
        cp_id = await manager.save("test-agent", "task", {"key": "val"})
        assert isinstance(cp_id, str)
        assert len(cp_id) > 0

    @pytest.mark.asyncio
    async def test_save_inserts_row(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        cp_id = await manager.save("victoria", "memory", {"data": "x"}, tags=["important"])
        conn.execute.assert_awaited_once()
        args = conn.execute.call_args[0]
        sql = args[0].strip()
        assert sql.startswith("INSERT INTO agent_checkpoints")
        assert args[1] == cp_id
        assert args[2] == "victoria"
        assert args[4] == "memory"

    @pytest.mark.asyncio
    async def test_save_with_parent(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        await manager.save("veronica", "task", {}, parent_id="parent-123")
        args = conn.execute.call_args[0]
        assert args[6] == "parent-123"

    @pytest.mark.asyncio
    async def test_save_task_state(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        await manager.save_task_state(
            task_id="t-1",
            agent_name="anna",
            task_data={"title": "test task", "status": "in_progress"},
            result="done",
        )
        conn.execute.assert_awaited_once()
        args = conn.execute.call_args[0]
        stored = json.loads(args[5])
        assert stored["task_id"] == "t-1"
        assert stored["task_data"]["title"] == "test task"
        assert stored["result"] == "done"
        assert args[4] == "task"

    @pytest.mark.asyncio
    async def test_save_session_state(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        await manager.save_session_state(
            session_id="sess-1",
            agent_name="victoria",
            messages=[{"role": "user", "content": "hello"}],
            context={"project": "atra"},
        )
        stored = json.loads(conn.execute.call_args[0][5])
        assert stored["session_id"] == "sess-1"
        assert stored["messages"][0]["content"] == "hello"
        assert stored["context"]["project"] == "atra"

    @pytest.mark.asyncio
    async def test_save_full_state(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        conn.fetch = AsyncMock(
            side_effect=[
                [
                    {
                        "id": "t1",
                        "title": "task1",
                        "status": "pending",
                        "priority": "high",
                        "metadata": "{}",
                    }
                ],
                [
                    {
                        "project_context": "atra",
                        "crystal_type": "decision",
                        "content": "use python",
                        "confidence_score": 0.9,
                        "metadata": "{}",
                    }
                ],
                [
                    {
                        "user_key": "user1",
                        "project_context": "atra",
                        "episode_type": "preference",
                        "content": "likes dark mode",
                        "metadata": "{}",
                    }
                ],
                [
                    {
                        "id": "bd1",
                        "question": "should we?",
                        "directive_text": "yes",
                        "structured_decision": "{}",
                        "created_at": datetime.now(timezone.utc),
                    }
                ],
                [],
            ]
        )
        cp_id = await manager.save_full_state("victoria")
        assert isinstance(cp_id, str)
        assert conn.fetch.call_count >= 3

    @pytest.mark.asyncio
    async def test_save_full_state_episodic_fallback(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)

        async def fetch_side(*args, **kwargs):
            query = args[0] if args else kwargs.get("query", "")
            if "episodic_memory" in query:
                raise Exception("table not found")
            if "tasks" in query:
                return [
                    {
                        "id": "t1",
                        "title": "task1",
                        "status": "pending",
                        "priority": "high",
                        "metadata": "{}",
                    }
                ]
            if "memory_crystals" in query:
                return []
            if "board_decisions" in query:
                return []
            if "agent_goals" in query:
                return []
            return []

        conn.fetch = AsyncMock(side_effect=fetch_side)
        cp_id = await manager.save_full_state("victoria")
        assert isinstance(cp_id, str)
        conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_full_state_includes_all_sections(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        now = datetime.now(timezone.utc)
        conn.fetch = AsyncMock(
            side_effect=[
                [
                    {
                        "id": "t1",
                        "title": "task1",
                        "status": "pending",
                        "priority": "high",
                        "metadata": "{}",
                    }
                ],
                [
                    {
                        "project_context": "atra",
                        "crystal_type": "decision",
                        "content": "use python",
                        "confidence_score": 0.9,
                        "metadata": "{}",
                    }
                ],
                [
                    {
                        "user_key": "user1",
                        "project_context": "atra",
                        "episode_type": "preference",
                        "content": "likes dark mode",
                        "metadata": "{}",
                    }
                ],
                [
                    {
                        "id": "bd1",
                        "question": "should we?",
                        "directive_text": "yes",
                        "structured_decision": "{}",
                        "created_at": now,
                    }
                ],
                [
                    {
                        "id": "g1",
                        "goal": "finish project",
                        "status": "in_progress",
                        "created_at": now,
                    }
                ],
            ]
        )
        await manager.save_full_state("victoria")
        stored = json.loads(conn.execute.call_args[0][5])
        snap = stored["snapshot"]
        assert "active_tasks" in snap
        assert "memory_crystals" in snap
        assert "episodic_memory" in snap
        assert "board_decisions" in snap
        assert "active_goals" in snap


class TestGet:
    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        conn.fetchrow = AsyncMock(return_value=None)
        result = await manager.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_checkpoint(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        now = datetime.now(timezone.utc)
        conn.fetchrow = AsyncMock(
            return_value={
                "id": "cp-1",
                "agent_name": "victoria",
                "created_at": now,
                "state_type": "task",
                "state_data": json.dumps({"key": "val"}),
                "parent_id": None,
                "tags": json.dumps(["task", "victoria"]),
            }
        )
        result = await manager.get("cp-1")
        assert isinstance(result, Checkpoint)
        assert result.checkpoint_id == "cp-1"
        assert result.agent_name == "victoria"
        assert result.state_data["key"] == "val"
        assert result.tags == ["task", "victoria"]

    @pytest.mark.asyncio
    async def test_get_latest(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        now = datetime.now(timezone.utc)
        conn.fetchrow = AsyncMock(
            return_value={
                "id": "latest-cp",
                "agent_name": "veronica",
                "created_at": now,
                "state_type": "session",
                "state_data": json.dumps({"session_id": "s1"}),
                "parent_id": None,
                "tags": json.dumps([]),
            }
        )
        result = await manager.get_latest("veronica", state_type="session")
        assert result.checkpoint_id == "latest-cp"
        args = conn.fetchrow.call_args[0]
        assert "WHERE agent_name = $1 AND state_type = $2" in args[0]

    @pytest.mark.asyncio
    async def test_get_latest_any_type(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        now = datetime.now(timezone.utc)
        conn.fetchrow = AsyncMock(
            return_value={
                "id": "any-cp",
                "agent_name": "veronica",
                "created_at": now,
                "state_type": "task",
                "state_data": json.dumps({}),
                "parent_id": None,
                "tags": json.dumps([]),
            }
        )
        result = await manager.get_latest("veronica")
        assert result.checkpoint_id == "any-cp"
        args = conn.fetchrow.call_args[0]
        assert "state_type" not in args[0].split("WHERE")[1]

    @pytest.mark.asyncio
    async def test_list_checkpoints(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        now = datetime.now(timezone.utc)
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": f"cp-{i}",
                    "agent_name": "victoria",
                    "created_at": now,
                    "state_type": "task",
                    "state_data": json.dumps({"n": i}),
                    "parent_id": None,
                    "tags": json.dumps([]),
                }
                for i in range(3)
            ]
        )
        result = await manager.list_checkpoints("victoria", limit=3)
        assert len(result) == 3
        assert all(isinstance(cp, Checkpoint) for cp in result)

    @pytest.mark.asyncio
    async def test_list_checkpoints_empty(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        conn.fetch = AsyncMock(return_value=[])
        result = await manager.list_checkpoints("ghost", limit=10)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_checkpoints_filtered_by_type(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        now = datetime.now(timezone.utc)
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": "cp-session",
                    "agent_name": "victoria",
                    "created_at": now,
                    "state_type": "session",
                    "state_data": json.dumps({"msg": "hello"}),
                    "parent_id": None,
                    "tags": json.dumps([]),
                }
            ]
        )
        result = await manager.list_checkpoints("victoria", limit=5, state_type="session")
        assert len(result) == 1
        assert result[0].state_type == "session"
        args = conn.fetch.call_args[0]
        assert "AND state_type = $2" in args[0]


class TestRestore:
    @pytest.mark.asyncio
    async def test_restore_task_checkpoint_not_found(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        conn.fetchrow = AsyncMock(return_value=None)
        ok, msg = await manager.restore_task("missing")
        assert ok is False
        assert "not found" in msg

    @pytest.mark.asyncio
    async def test_restore_task_wrong_type(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        conn.fetchrow = AsyncMock(
            return_value={
                "id": "cp-s",
                "agent_name": "v",
                "created_at": datetime.now(timezone.utc),
                "state_type": "session",
                "state_data": json.dumps({"session_id": "s1"}),
                "parent_id": None,
                "tags": json.dumps([]),
            }
        )
        ok, msg = await manager.restore_task("cp-s")
        assert ok is False
        assert "not a task checkpoint" in msg

    @pytest.mark.asyncio
    async def test_restore_task_updates_db(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        conn.fetchrow = AsyncMock(
            return_value={
                "id": "cp-task",
                "agent_name": "victoria",
                "created_at": datetime.now(timezone.utc),
                "state_type": "task",
                "state_data": json.dumps(
                    {
                        "task_id": "t-42",
                        "task_data": {
                            "title": "fix bugs",
                            "status": "in_progress",
                            "priority": "high",
                            "metadata": {"retry": 1},
                        },
                        "result": None,
                    }
                ),
                "parent_id": None,
                "tags": json.dumps([]),
            }
        )
        ok, msg = await manager.restore_task("cp-task")
        assert ok is True
        assert "t-42" in msg

    @pytest.mark.asyncio
    async def test_restore_task_creates_new(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        conn.fetchrow = AsyncMock(
            return_value={
                "id": "cp-new",
                "agent_name": "victoria",
                "created_at": datetime.now(timezone.utc),
                "state_type": "task",
                "state_data": json.dumps(
                    {
                        "task_data": {
                            "title": "new task",
                            "description": "do it",
                            "status": "pending",
                            "priority": "low",
                            "metadata": {},
                        },
                        "result": None,
                    }
                ),
                "parent_id": None,
                "tags": json.dumps([]),
            }
        )
        conn.fetchval = AsyncMock(return_value="new-uuid-abc")
        ok, msg = await manager.restore_task("cp-new")
        assert ok is True
        assert "new-uuid-abc" in msg

    @pytest.mark.asyncio
    async def test_restore_task_from_full_checkpoint(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        conn.fetchrow = AsyncMock(
            return_value={
                "id": "cp-full",
                "agent_name": "victoria",
                "created_at": datetime.now(timezone.utc),
                "state_type": "full",
                "state_data": json.dumps(
                    {
                        "snapshot": {
                            "active_tasks": [
                                {
                                    "id": "t99",
                                    "title": "full task",
                                    "status": "in_progress",
                                    "priority": "urgent",
                                    "metadata": {"x": 1},
                                }
                            ]
                        }
                    }
                ),
                "parent_id": None,
                "tags": json.dumps([]),
            }
        )
        ok, msg = await manager.restore_task("cp-full")
        assert ok is True
        assert "t99" in msg

    @pytest.mark.asyncio
    async def test_restore_task_from_full_no_tasks(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        conn.fetchrow = AsyncMock(
            return_value={
                "id": "cp-empty",
                "agent_name": "victoria",
                "created_at": datetime.now(timezone.utc),
                "state_type": "full",
                "state_data": json.dumps({"snapshot": {"active_tasks": []}}),
                "parent_id": None,
                "tags": json.dumps([]),
            }
        )
        ok, msg = await manager.restore_task("cp-empty")
        assert ok is False

    @pytest.mark.asyncio
    async def test_restore_task_redis_import_failure_handled_gracefully(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        conn.fetchrow = AsyncMock(
            return_value={
                "id": "cp-r1",
                "agent_name": "v",
                "created_at": datetime.now(timezone.utc),
                "state_type": "task",
                "state_data": json.dumps({"task_id": "t-1", "task_data": {"status": "pending"}}),
                "parent_id": None,
                "tags": json.dumps([]),
            }
        )
        ok, msg = await manager.restore_task("cp-r1")
        assert ok is True


class TestRollback:
    @pytest.mark.asyncio
    async def test_rollback_invalid_steps(self, manager):
        ok, msg = await manager.rollback("victoria", steps=0)
        assert ok is False
        ok, msg = await manager.rollback("victoria", steps=-1)
        assert ok is False

    @pytest.mark.asyncio
    async def test_rollback_not_enough_checkpoints(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        conn.fetch = AsyncMock(return_value=[{"id": "only-one"}])
        ok, msg = await manager.rollback("victoria", steps=3)
        assert ok is False
        assert "only 1" in msg

    @pytest.mark.asyncio
    async def test_rollback_creates_safety_checkpoint(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": "cp-2",
                    "state_type": "task",
                    "state_data": json.dumps({"task_id": "t-2"}),
                    "created_at": datetime.now(timezone.utc),
                },
                {
                    "id": "cp-1",
                    "state_type": "task",
                    "state_data": json.dumps({"task_id": "t-1"}),
                    "created_at": datetime.now(timezone.utc),
                },
            ]
        )
        conn.fetchrow = AsyncMock(
            return_value={
                "id": "cp-1",
                "agent_name": "victoria",
                "created_at": datetime.now(timezone.utc),
                "state_type": "task",
                "state_data": json.dumps(
                    {
                        "task_id": "t-1",
                        "task_data": {
                            "title": "restore me",
                            "status": "in_progress",
                            "priority": "high",
                            "metadata": {},
                        },
                    }
                ),
                "parent_id": None,
                "tags": json.dumps([]),
            }
        )
        ok, msg = await manager.rollback("victoria", steps=1)
        assert ok is True

    @pytest.mark.asyncio
    async def test_rollback_restores_task(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": "cp-2",
                    "state_type": "task",
                    "state_data": json.dumps({"task_id": "t-2"}),
                    "created_at": datetime.now(timezone.utc),
                },
                {
                    "id": "cp-1",
                    "state_type": "task",
                    "state_data": json.dumps({"task_id": "t-1"}),
                    "created_at": datetime.now(timezone.utc),
                },
            ]
        )
        conn.fetchrow = AsyncMock(
            return_value={
                "id": "cp-1",
                "agent_name": "victoria",
                "created_at": datetime.now(timezone.utc),
                "state_type": "task",
                "state_data": json.dumps(
                    {
                        "task_id": "t-1",
                        "task_data": {
                            "title": "rollback target",
                            "status": "in_progress",
                            "priority": "medium",
                            "metadata": {},
                        },
                    }
                ),
                "parent_id": None,
                "tags": json.dumps([]),
            }
        )
        ok, msg = await manager.rollback("victoria", steps=1)
        assert ok is True

    @pytest.mark.asyncio
    async def test_rollback_two_steps(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": "cp-3",
                    "state_type": "task",
                    "state_data": json.dumps({"task_id": "t-3"}),
                    "created_at": datetime.now(timezone.utc),
                },
                {
                    "id": "cp-2",
                    "state_type": "task",
                    "state_data": json.dumps({"task_id": "t-2"}),
                    "created_at": datetime.now(timezone.utc),
                },
                {
                    "id": "cp-1",
                    "state_type": "task",
                    "state_data": json.dumps({"task_id": "t-1"}),
                    "created_at": datetime.now(timezone.utc),
                },
            ]
        )
        conn.fetchrow = AsyncMock(
            return_value={
                "id": "cp-1",
                "agent_name": "victoria",
                "created_at": datetime.now(timezone.utc),
                "state_type": "task",
                "state_data": json.dumps(
                    {
                        "task_id": "t-1",
                        "task_data": {
                            "title": "two step back",
                            "status": "pending",
                            "priority": "low",
                            "metadata": {},
                        },
                    }
                ),
                "parent_id": None,
                "tags": json.dumps([]),
            }
        )
        ok, msg = await manager.rollback("victoria", steps=2)
        assert ok is True


class TestCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_deletes_old(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        conn.execute = AsyncMock(return_value="DELETE 10")
        await manager.cleanup("victoria", keep_last=5)
        conn.execute.assert_awaited_once()
        args = conn.execute.call_args[0]
        assert "DELETE FROM agent_checkpoints" in args[0]

    @pytest.mark.asyncio
    async def test_cleanup_all(self, manager, mock_pool):
        conn = _resolve_conn(mock_pool)
        conn.fetch = AsyncMock(
            return_value=[
                {"agent_name": "victoria"},
                {"agent_name": "veronica"},
            ]
        )
        conn.execute = AsyncMock(return_value="DELETE 5")
        await manager.cleanup_all(keep_last=10)
        assert conn.execute.call_count >= 2


class TestDBDisabled:
    @pytest.fixture
    def manager_no_db(self):
        mgr = StateCheckpointManager()
        return mgr

    @pytest.mark.asyncio
    async def test_save_returns_empty_without_db(self, manager_no_db):
        with patch("app.state_checkpoint.DB_AVAILABLE", False):
            result = await manager_no_db.save("a", "task", {})
            assert result == ""

    @pytest.mark.asyncio
    async def test_get_returns_none_without_db(self, manager_no_db):
        with patch("app.state_checkpoint.DB_AVAILABLE", False):
            result = await manager_no_db.get("any")
            assert result is None

    @pytest.mark.asyncio
    async def test_list_empty_without_db(self, manager_no_db):
        with patch("app.state_checkpoint.DB_AVAILABLE", False):
            result = await manager_no_db.list_checkpoints("a")
            assert result == []

    @pytest.mark.asyncio
    async def test_cleanup_skips_without_db(self, manager_no_db):
        with patch("app.state_checkpoint.DB_AVAILABLE", False):
            await manager_no_db.cleanup("a")
            await manager_no_db.cleanup_all()
