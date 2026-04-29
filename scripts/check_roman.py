import asyncpg
import asyncio
import os
import json

async def check():
    pool = await asyncpg.create_pool(os.getenv('DATABASE_URL'))
    async with pool.acquire() as conn:
        print("--- Tasks in Progress or R&D ---")
        rows = await conn.fetch("""
            SELECT id, status, updated_at, metadata 
            FROM tasks 
            WHERE status = 'in_progress' 
               OR id::text LIKE 'RD_%' 
            ORDER BY updated_at DESC 
            LIMIT 10
        """)
        for r in rows:
            print(f"ID: {r['id']} | Status: {r['status']} | Updated: {r['updated_at']}")
            
        print("\n--- Recent Actor Events for 'Роман' ---")
        events = await conn.fetch("""
            SELECT event_type, created_at, payload 
            FROM actor_events 
            WHERE actor_name = 'Роман' 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        for e in events:
            print(f"Event: {e['event_type']} | Created: {e['created_at']} | Payload: {e['payload'][:100]}...")
            
    await pool.close()

if __name__ == "__main__":
    asyncio.run(check())
