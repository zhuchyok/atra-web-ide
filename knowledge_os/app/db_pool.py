"""
Единая точка доступа к пулу БД Knowledge OS.

Используется в rest_api, collective_memory и др. При будущем переводе на Rust
здесь можно заменить asyncpg на обёртку над Rust-пулом (тот же контракт: get_pool() -> pool, pool.acquire()).
"""
import os
import asyncpg

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

_pool = None


async def get_pool():
    """Ленивая инициализация пула. Возвращает asyncpg Pool (или в будущем — обёртку над Rust)."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DB_URL,
            min_size=1,
            max_size=10,
            max_inactive_connection_lifetime=300,
            command_timeout=60,
        )
    return _pool
