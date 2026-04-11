"""
Integration tests for RedTeamAuditor (knowledge_os/app/red_team_auditor.py).

Strategy:
- _audit_node / _audit_task / _report_breach tested with mocked LLM (no real Victoria call).
- run_audit_cycle tested end-to-end against real DB with seeded nodes/tasks.
- Verifies that a breach task is created in `tasks` when auditor detects a problem.

Run: pytest knowledge_os/tests/test_red_team_auditor.py -v
"""

import asyncio
import json
import sys
import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_APP_DIR))

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os"),
)


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
    conn = await asyncpg.connect(TEST_DB_URL)
    yield conn
    await conn.close()


@pytest.fixture
async def seed_knowledge_node(db_conn):
    """Создаёт временный узел знаний для тестов аудита."""
    # Получаем первый домен (нужен для FK)
    domain_id = await db_conn.fetchval(
        "SELECT id FROM domains ORDER BY created_at LIMIT 1"
    )
    if not domain_id:
        domain_id = await db_conn.fetchval(
            "INSERT INTO domains (name) VALUES ('test_audit_domain') RETURNING id"
        )

    node_id = await db_conn.fetchval(
        """
        INSERT INTO knowledge_nodes (domain_id, content, is_verified, metadata)
        VALUES ($1, $2, TRUE, $3)
        RETURNING id
        """,
        domain_id,
        "TEST: The sky is green and the sun rises in the west.",
        json.dumps({"source": "test"}),
    )
    yield node_id
    await db_conn.execute("DELETE FROM knowledge_nodes WHERE id = $1", node_id)


@pytest.fixture
async def seed_completed_task(db_conn):
    """Создаёт завершённую задачу для тестов аудита."""
    task_id = await db_conn.fetchval(
        """
        INSERT INTO tasks (title, description, status, result, metadata)
        VALUES ($1, $2, 'completed', $3, $4)
        RETURNING id
        """,
        "test_audit_task_" + str(uuid.uuid4())[:8],
        "Тестовая задача для Red Team Auditor",
        "Результат: утверждается что 2+2=5 без доказательств.",
        json.dumps({"source": "test"}),
    )
    yield task_id
    await db_conn.execute("DELETE FROM tasks WHERE id = $1", task_id)
    # Удаляем задачи-нарушения, созданные аудитором для этой задачи
    await db_conn.execute(
        "DELETE FROM tasks WHERE metadata->>'source' = 'red_team_auditor' "
        "AND metadata->>'origin' LIKE $1",
        f"Task {task_id}%",
    )


# ---------------------------------------------------------------------------
# Import auditor (skip if asyncpg or app not available)
# ---------------------------------------------------------------------------

def _import_auditor():
    try:
        from red_team_auditor import RedTeamAuditor
        return RedTeamAuditor
    except Exception:
        return None


# ===========================================================================
# UNIT TESTS (mocked LLM)
# ===========================================================================


@pytest.mark.asyncio
async def test_report_breach_creates_task(db_conn):
    """_report_breach должен создавать задачу с приоритетом high."""
    RedTeamAuditor = _import_auditor()
    if RedTeamAuditor is None:
        pytest.skip("RedTeamAuditor не доступен")

    auditor = RedTeamAuditor(db_url=TEST_DB_URL)
    source = f"Test Source {uuid.uuid4()}"
    report = '{"problem": "contradiction detected", "severity": "high"}'

    await auditor._report_breach(db_conn, source, report)

    row = await db_conn.fetchrow(
        "SELECT title, priority, metadata FROM tasks WHERE title = $1",
        f"🚨 LOGIC BREACH: {source}",
    )
    assert row is not None, "Задача-нарушение должна быть создана"
    assert row["priority"] == "high"
    meta = json.loads(row["metadata"])
    assert meta["source"] == "red_team_auditor"
    assert meta["origin"] == source

    # Cleanup
    await db_conn.execute("DELETE FROM tasks WHERE title = $1", f"🚨 LOGIC BREACH: {source}")


@pytest.mark.asyncio
async def test_audit_node_triggers_breach_on_problem(db_conn, seed_knowledge_node):
    """_audit_node должен вызвать _report_breach если LLM находит проблему."""
    RedTeamAuditor = _import_auditor()
    if RedTeamAuditor is None:
        pytest.skip("RedTeamAuditor не доступен")

    node_row = await db_conn.fetchrow(
        "SELECT id, content, metadata FROM knowledge_nodes WHERE id = $1",
        seed_knowledge_node,
    )
    fake_llm_response = '{"problem": "factual error: sky is not green", "severity": "high"}'

    auditor = RedTeamAuditor(db_url=TEST_DB_URL)
    breach_source = None

    async def mock_report(conn, source, report):
        nonlocal breach_source
        breach_source = source

    auditor._report_breach = mock_report

    with patch("red_team_auditor.run_smart_agent_async", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = fake_llm_response
        await auditor._audit_node(db_conn, node_row)

    assert breach_source is not None, "_report_breach должен быть вызван при обнаружении проблемы"
    assert str(seed_knowledge_node) in breach_source


@pytest.mark.asyncio
async def test_audit_node_no_breach_on_ok(db_conn, seed_knowledge_node):
    """_audit_node НЕ должен создавать брич если LLM вернул 'OK'."""
    RedTeamAuditor = _import_auditor()
    if RedTeamAuditor is None:
        pytest.skip("RedTeamAuditor не доступен")

    node_row = await db_conn.fetchrow(
        "SELECT id, content, metadata FROM knowledge_nodes WHERE id = $1",
        seed_knowledge_node,
    )
    auditor = RedTeamAuditor(db_url=TEST_DB_URL)
    breach_called = False

    async def mock_report(conn, source, report):
        nonlocal breach_called
        breach_called = True

    auditor._report_breach = mock_report

    with patch("red_team_auditor.run_smart_agent_async", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "OK"
        await auditor._audit_node(db_conn, node_row)

    assert not breach_called, "Брич не должен создаваться при ответе LLM 'OK'"


@pytest.mark.asyncio
async def test_audit_task_triggers_breach(db_conn, seed_completed_task):
    """_audit_task должен вызвать _report_breach при обнаружении логической ошибки."""
    RedTeamAuditor = _import_auditor()
    if RedTeamAuditor is None:
        pytest.skip("RedTeamAuditor не доступен")

    task_row = await db_conn.fetchrow(
        "SELECT id, title, result FROM tasks WHERE id = $1", seed_completed_task
    )
    fake_response = '{"problem": "2+2=5 is incorrect", "severity": "medium"}'

    auditor = RedTeamAuditor(db_url=TEST_DB_URL)
    breach_called = False

    async def mock_report(conn, source, report):
        nonlocal breach_called
        breach_called = True

    auditor._report_breach = mock_report

    with patch("red_team_auditor.run_smart_agent_async", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = fake_response
        await auditor._audit_task(db_conn, task_row)

    assert breach_called


@pytest.mark.asyncio
async def test_audit_task_no_breach_on_ok(db_conn, seed_completed_task):
    """_audit_task НЕ должен создавать брич при ответе 'OK'."""
    RedTeamAuditor = _import_auditor()
    if RedTeamAuditor is None:
        pytest.skip("RedTeamAuditor не доступен")

    task_row = await db_conn.fetchrow(
        "SELECT id, title, result FROM tasks WHERE id = $1", seed_completed_task
    )
    auditor = RedTeamAuditor(db_url=TEST_DB_URL)
    breach_called = False

    async def mock_report(conn, source, report):
        nonlocal breach_called
        breach_called = True

    auditor._report_breach = mock_report

    with patch("red_team_auditor.run_smart_agent_async", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "OK"
        await auditor._audit_task(db_conn, task_row)

    assert not breach_called


# ===========================================================================
# INTEGRATION TEST — run_audit_cycle end-to-end
# ===========================================================================


@pytest.mark.asyncio
async def test_run_audit_cycle_does_not_crash(db_conn):
    """run_audit_cycle должен завершаться без исключений (LLM замокан → 'OK')."""
    RedTeamAuditor = _import_auditor()
    if RedTeamAuditor is None:
        pytest.skip("RedTeamAuditor не доступен")

    auditor = RedTeamAuditor(db_url=TEST_DB_URL)

    with patch("red_team_auditor.run_smart_agent_async", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "OK"
        # Должен завершиться без исключений
        await auditor.run_audit_cycle()


@pytest.mark.asyncio
async def test_run_audit_cycle_creates_breach_task(db_conn, seed_knowledge_node):
    """run_audit_cycle должен создать задачу-нарушение при ответе LLM с проблемой."""
    RedTeamAuditor = _import_auditor()
    if RedTeamAuditor is None:
        pytest.skip("RedTeamAuditor не доступен")

    # Считаем задачи с source=red_team_auditor до запуска
    before = await db_conn.fetchval(
        "SELECT COUNT(*) FROM tasks WHERE metadata->>'source' = 'red_team_auditor'"
    )

    auditor = RedTeamAuditor(db_url=TEST_DB_URL)

    with patch("red_team_auditor.run_smart_agent_async", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = '{"problem": "test breach", "severity": "high"}'
        await auditor.run_audit_cycle()

    after = await db_conn.fetchval(
        "SELECT COUNT(*) FROM tasks WHERE metadata->>'source' = 'red_team_auditor'"
    )
    assert after > before, "Аудитор должен создавать задачи-нарушения в БД"

    # Cleanup
    await db_conn.execute(
        "DELETE FROM tasks WHERE metadata->>'source' = 'red_team_auditor'"
    )
