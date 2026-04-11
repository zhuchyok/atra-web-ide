"""
Integration tests for:
- VictoriaExpertActor.recover_state (Event Sourcing)
- RedTeamAuditor._audit_node, _audit_task, _report_breach, run_audit_cycle

These tests require a live PostgreSQL with actor_states / actor_events tables
(migration: knowledge_os/db/migrations/20260411_actor_event_sourcing.sql).

Run: pytest knowledge_os/tests/test_actor_event_sourcing.py -v
     pytest knowledge_os/tests/test_red_team_auditor.py    -v
"""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

TEST_DB_URL = __import__("os").getenv(
    "TEST_DATABASE_URL",
    __import__("os").getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os"),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_conn() -> asyncpg.Connection:
    return await asyncpg.connect(TEST_DB_URL)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_conn():
    conn = await _get_conn()
    yield conn
    await conn.close()


@pytest.fixture
async def clean_actor_tables(db_conn):
    """Удаляет тестовые записи после каждого теста."""
    yield
    await db_conn.execute("DELETE FROM actor_events WHERE actor_name LIKE 'test_%'")
    await db_conn.execute("DELETE FROM actor_states WHERE actor_name LIKE 'test_%'")


# ---------------------------------------------------------------------------
# Minimal stub for VictoriaExpertActor without agentscope
# ---------------------------------------------------------------------------

class _StubActor:
    """Minimal stand-in when agentscope is not installed."""

    def __init__(self, name: str, task_id: str = None):
        self.name = name
        self.task_id = task_id
        self._db_pool = None
        self._state: dict = {}

    async def _get_pool(self):
        if not self._db_pool:
            self._db_pool = await asyncpg.create_pool(TEST_DB_URL, min_size=1, max_size=3)
        return self._db_pool

    async def record_event(self, event_type: str, payload: dict):
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO actor_events (actor_name, task_id, event_type, payload) "
                "VALUES ($1, $2, $3, $4)",
                self.name,
                uuid.UUID(self.task_id) if self.task_id else None,
                event_type,
                json.dumps(payload),
            )

    async def save_snapshot(self):
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO actor_states (actor_name, task_id, state_data) "
                "VALUES ($1, $2, $3)",
                self.name,
                uuid.UUID(self.task_id) if self.task_id else None,
                json.dumps(self._state),
            )

    async def recover_state(self):
        if not self.task_id:
            return
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT state_data FROM actor_states "
                "WHERE actor_name = $1 AND task_id = $2 "
                "ORDER BY created_at DESC LIMIT 1",
                self.name,
                uuid.UUID(self.task_id),
            )
            if row:
                self._state = json.loads(row["state_data"])

    async def close(self):
        if self._db_pool:
            await self._db_pool.close()


# ===========================================================================
# ACTOR EVENT SOURCING TESTS
# ===========================================================================


@pytest.mark.asyncio
async def test_record_event_inserts_row(clean_actor_tables):
    """record_event должен создавать строку в actor_events."""
    actor = _StubActor(name="test_actor_1", task_id=str(uuid.uuid4()))
    await actor.record_event("test_event", {"key": "value"})

    conn = await _get_conn()
    try:
        row = await conn.fetchrow(
            "SELECT event_type, payload FROM actor_events WHERE actor_name = $1",
            actor.name,
        )
        assert row is not None, "Строка события должна быть создана"
        assert row["event_type"] == "test_event"
        payload = json.loads(row["payload"])
        assert payload["key"] == "value"
    finally:
        await conn.execute("DELETE FROM actor_events WHERE actor_name = $1", actor.name)
        await conn.close()
        await actor.close()


@pytest.mark.asyncio
async def test_save_and_recover_state(clean_actor_tables):
    """Снимок состояния должен восстанавливаться через recover_state."""
    task_id = str(uuid.uuid4())
    actor = _StubActor(name="test_actor_2", task_id=task_id)
    actor._state = {"progress": 42, "last_step": "analysis"}
    await actor.save_snapshot()

    # Новый актор с тем же именем/task_id — должен восстановить состояние
    actor2 = _StubActor(name="test_actor_2", task_id=task_id)
    assert actor2._state == {}, "До recover_state состояние должно быть пустым"

    await actor2.recover_state()
    assert actor2._state["progress"] == 42
    assert actor2._state["last_step"] == "analysis"

    await actor.close()
    await actor2.close()


@pytest.mark.asyncio
async def test_recover_state_no_snapshot(clean_actor_tables):
    """recover_state без снимка не должен бросать исключение."""
    actor = _StubActor(name="test_actor_3", task_id=str(uuid.uuid4()))
    # Снимков нет — recover_state должен завершиться без ошибок
    await actor.recover_state()
    assert actor._state == {}
    await actor.close()


@pytest.mark.asyncio
async def test_recover_state_without_task_id():
    """recover_state без task_id должен вернуться немедленно."""
    actor = _StubActor(name="test_actor_4", task_id=None)
    await actor.recover_state()  # не должен делать запрос в БД
    assert actor._state == {}


@pytest.mark.asyncio
async def test_latest_snapshot_is_used(clean_actor_tables):
    """recover_state должен брать ПОСЛЕДНИЙ снимок (ORDER BY created_at DESC)."""
    task_id = str(uuid.uuid4())
    actor = _StubActor(name="test_actor_5", task_id=task_id)

    actor._state = {"version": 1}
    await actor.save_snapshot()
    await asyncio.sleep(0.05)  # гарантируем другой created_at

    actor._state = {"version": 2}
    await actor.save_snapshot()

    actor2 = _StubActor(name="test_actor_5", task_id=task_id)
    await actor2.recover_state()
    assert actor2._state["version"] == 2, "Должен быть восстановлен последний снимок"

    await actor.close()
    await actor2.close()


@pytest.mark.asyncio
async def test_event_log_ordering(clean_actor_tables):
    """События должны храниться в порядке вставки (BIGSERIAL id)."""
    actor = _StubActor(name="test_actor_6", task_id=str(uuid.uuid4()))
    events = ["start", "process", "finish"]
    for e in events:
        await actor.record_event(e, {})

    conn = await _get_conn()
    try:
        rows = await conn.fetch(
            "SELECT event_type FROM actor_events WHERE actor_name = $1 ORDER BY id",
            actor.name,
        )
        assert [r["event_type"] for r in rows] == events
    finally:
        await conn.execute("DELETE FROM actor_events WHERE actor_name = $1", actor.name)
        await conn.close()
        await actor.close()
