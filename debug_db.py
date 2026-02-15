import asyncpg
import asyncio
import os

async def test():
    try:
        conn = await asyncpg.connect('postgresql://admin:secret@localhost:5432/knowledge_os')
        rows = await conn.fetch('SELECT count(*) FROM experts')
        print(f'Experts count: {rows[0][0]}')
        
        # Also check domains
        domains = await conn.fetch('SELECT name FROM domains')
        print(f'Domains: {[d[0] for d in domains]}')
        
        await conn.close()
    except Exception as e:
        print(f'Database error: {e}')

if __name__ == "__main__":
    asyncio.run(test())
