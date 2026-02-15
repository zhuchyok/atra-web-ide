"""
Pytest configuration and fixtures
"""

import os
import sys
import time
from pathlib import Path

import pytest
import asyncio
import asyncpg
from typing import AsyncGenerator

# Путь к проекту: conftest в knowledge_os/tests/, родитель = knowledge_os/, parent.parent = atra-web-ide
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Test database URL: fallback на knowledge_os если _test недоступна
TEST_DB_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or "postgresql://admin:secret@localhost:5432/knowledge_os"


@pytest.fixture(scope="session")
def wait_for_victoria():
    """
    Ожидание готовности Victoria перед интеграционными тестами (session-scoped).
    До 60 с опрашивает GET {VICTORIA_URL}/health; при неудаче — pytest.fail.
    """
    try:
        import requests
    except ImportError:
        pytest.skip("requests не установлен")
    base = os.getenv("VICTORIA_URL", "http://localhost:8010").rstrip("/")
    url = f"{base}/health"
    timeout = 60
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    pytest.fail(f"Victoria не ответила на {url} за {timeout} с. Запустите: docker compose -f knowledge_os/docker-compose.yml up -d")


@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Database connection fixture"""
    conn = await asyncpg.connect(TEST_DB_URL)
    try:
        yield conn
    finally:
        await conn.close()


@pytest.fixture
async def test_domain_id(db_connection):
    """Create test domain and return ID"""
    domain_id = await db_connection.fetchval("""
        INSERT INTO domains (name) 
        VALUES ('Test Domain E2E ' || gen_random_uuid()::text)
        RETURNING id
    """)
    yield domain_id
    # Cleanup: сначала knowledge_nodes и knowledge_links, потом domains (FK)
    await db_connection.execute(
        "DELETE FROM knowledge_nodes WHERE domain_id = $1", domain_id
    )
    await db_connection.execute("DELETE FROM domains WHERE id = $1", domain_id)


@pytest.fixture
async def test_expert_id(db_connection):
    """Create test expert and return ID"""
    expert_id = await db_connection.fetchval("""
        INSERT INTO experts (name, role, system_prompt, department)
        VALUES ('Test Expert', 'Test Role', 'Test prompt', 'Test Department')
        ON CONFLICT (name) DO UPDATE SET name = 'Test Expert'
        RETURNING id
    """)
    yield expert_id
    # Cleanup: сначала все зависимости (FK → experts), потом эксперт
    await db_connection.execute("DELETE FROM adaptive_learning_logs WHERE expert_id = $1", expert_id)
    await db_connection.execute(
        "DELETE FROM tasks WHERE assignee_expert_id = $1 OR creator_expert_id = $1",
        expert_id,
    )
    await db_connection.execute("DELETE FROM interaction_logs WHERE expert_id = $1", expert_id)
    await db_connection.execute("DELETE FROM experts WHERE id = $1", expert_id)


@pytest.fixture
async def knowledge_nodes_id_is_uuid(db_connection) -> bool:
    """True если knowledge_nodes.id имеет тип uuid (иначе тесты links требуют skip)."""
    try:
        row = await db_connection.fetchrow(
            "SELECT data_type FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'knowledge_nodes' AND column_name = 'id'"
        )
        return row and str(row["data_type"]).lower() == "uuid"
    except Exception:
        return False

