"""
Единая точка доступа к пулу БД Knowledge OS.

Используется в rest_api, collective_memory и др. При будущем переводе на Rust
здесь можно заменить asyncpg на обёртку над Rust-пулом (тот же контракт: get_pool() -> pool, pool.acquire()).

Best practices (2026, 12-Factor + asyncpg):
- max_size=5: при 39+ модулях каждый с пулом суммарный лимит ~300-400 → легко достигает max_connections=500.
  Уменьшение до 5 снижает пиковое потребление; при необходимости — PgBouncer перед Postgres.
- max_inactive_connection_lifetime=300: закрывает idle-соединения через 5 мин (освобождает слоты).
- command_timeout=30: гарантирует, что зависший запрос не держит соединение вечно.
"""

import os

import asyncpg

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

# Читаем из env, чтобы можно было тюнить без rebuild (например, при включённом PgBouncer ставим 20)
_MAX_POOL_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "5"))
_MIN_POOL_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "1"))

_pool = None


async def get_pool():
    """Ленивая инициализация пула. Возвращает asyncpg Pool (или в будущем — обёртку над Rust)."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DB_URL,
            min_size=_MIN_POOL_SIZE,
            max_size=_MAX_POOL_SIZE,
            max_inactive_connection_lifetime=300,
            command_timeout=30,
        )
    return _pool


async def close_pool():
    """Явное закрытие пула при shutdown (освобождает все соединения сразу)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
