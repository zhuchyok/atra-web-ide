#!/usr/bin/env python3
import asyncio
import os
import asyncpg
import getpass

async def check():
    db_url = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
    
    conn = await asyncpg.connect(db_url)
    try:
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name LIKE '%routing%' OR table_name LIKE '%router%'
        """)
        print('Таблицы:', [r['table_name'] for r in tables])
        
        # Проверяем структуру таблицы
        if tables:
            for table in tables:
                cols = await conn.fetch(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{table['table_name']}'
                    ORDER BY ordinal_position
                """)
                print(f"\nКолонки {table['table_name']}:")
                for col in cols:
                    print(f"  - {col['column_name']}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check())

