import asyncio
import asyncpg
import os

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

async def check_schema():
    conn = await asyncpg.connect(DB_URL)
    try:
        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'experts'
        """)
        print("Columns in 'experts' table:")
        for col in columns:
            print(f"- {col['column_name']}: {col['data_type']}")

        # Также проверим первые несколько записей, чтобы увидеть реальные данные
        rows = await conn.fetch("SELECT * FROM experts LIMIT 3")
        if rows:
            print("\nSample data:")
            for row in rows:
                print(dict(row))
        else:
            print("\nNo data in 'experts' table.")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_schema())
