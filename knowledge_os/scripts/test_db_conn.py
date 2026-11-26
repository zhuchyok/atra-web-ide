import asyncio
import os

import asyncpg


async def t():
    db_url = os.getenv("DATABASE_URL")
    print(f"Connecting to {db_url}")
    try:
        conn = await asyncpg.connect(db_url)
        count = await conn.fetchval("SELECT count(*) FROM experts")
        print(f"Table experts count: {count}")
        res = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'experts' AND column_name = 'specialization_level'"
        )
        print(f"specialization_level exists: {len(res) > 0}")

        # Check all tables
        tables = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        print(f"Total tables: {len(tables)}")

        await conn.close()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(t())
