"""
Pytest configuration and fixtures
"""

import os
import sys
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
    # Cleanup
    await db_connection.execute("DELETE FROM experts WHERE id = $1", expert_id)

