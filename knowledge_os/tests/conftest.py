"""
Pytest configuration and fixtures
"""

import pytest
import asyncio
import asyncpg
import os
from typing import AsyncGenerator

# Test database URL (можно использовать отдельную тестовую БД)
TEST_DB_URL = os.getenv('TEST_DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os_test')


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
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
        VALUES ('Test Domain')
        ON CONFLICT (name) DO UPDATE SET name = 'Test Domain'
        RETURNING id
    """)
    yield domain_id
    # Cleanup
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

