#!/usr/bin/env python3
"""Применить миграцию add_orchestrator_version (колонка orchestrator_version в tasks)."""
import asyncio
import os
import sys

_REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

try:
    import asyncpg
except ImportError:
    print("asyncpg not installed. Run migration one of:")
    print("  1. pip install asyncpg && python3 scripts/run_orchestrator_version_migration.py")
    print("  2. From project root: docker compose -f knowledge_os/docker-compose.yml exec knowledge_postgres psql -U admin -d knowledge_os -f - < knowledge_os/db/migrations/add_orchestrator_version.sql")
    print("  3. psql $DATABASE_URL -f knowledge_os/db/migrations/add_orchestrator_version.sql")
    sys.exit(1)


async def main():
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    migration_path = os.path.join(_REPO, "knowledge_os", "db", "migrations", "add_orchestrator_version.sql")
    if not os.path.exists(migration_path):
        print("Migration file not found:", migration_path)
        sys.exit(1)
    sql = open(migration_path, "r").read()
    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute(sql)
        print("Migration add_orchestrator_version applied.")
    except Exception as e:
        print("Migration error:", e)
        sys.exit(1)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
