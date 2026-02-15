import asyncpg
import asyncio
import os

async def test():
    try:
        # Try both localhost (if port forwarded) and knowledge_postgres (Docker network)
        urls = [
            'postgresql://admin:secret@knowledge_postgres:5432/knowledge_os',
            'postgresql://admin:secret@localhost:5432/knowledge_os'
        ]
        for url in urls:
            print(f"Testing URL: {url}")
            try:
                conn = await asyncpg.connect(url, timeout=5)
                rows = await conn.fetch('SELECT count(*) FROM experts')
                print(f'Success! Experts count: {rows[0][0]}')
                await conn.close()
                return
            except Exception as e:
                print(f'Failed {url}: {e}')
    except Exception as e:
        print(f'General error: {e}')

if __name__ == "__main__":
    asyncio.run(test())
