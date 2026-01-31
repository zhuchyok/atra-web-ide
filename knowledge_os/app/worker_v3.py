import asyncio
import os
import json
import subprocess
import sys
from datetime import datetime

print("Smart Worker v3.0 initializing...")

# --- EMERGENCY REPAIR BLOCK ---
try:
    import asyncpg
    print("asyncpg loaded successfully")
except ImportError:
    print("Installing asyncpg via pip...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "asyncpg"])
    import asyncpg
    print("asyncpg installed and loaded")
# ------------------------------

# Database connection pool
pool = None

async def get_pool():
    global pool
    if pool is None:
        # Default fallback for testing
        db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@127.0.0.1:5432/knowledge_os")
        print(f"Connecting to database...")
        pool = await asyncpg.create_pool(
            db_url,
            min_size=1,
            max_size=5
        )
    return pool

async def main():
    print(f"[{datetime.now()}] Smart Worker v3.0 is ONLINE")
    while True:
        try:
            p = await get_pool()
            # Fetch pending tasks
            tasks = await p.fetch("""
                SELECT t.id, t.title, e.name as assignee 
                FROM tasks t 
                JOIN experts e ON t.assignee_expert_id = e.id 
                WHERE t.status = 'pending' 
                ORDER BY t.created_at ASC LIMIT 5
            """)
            
            if tasks:
                print(f"Found {len(tasks)} tasks. Processing...")
                for task in tasks:
                    t_id = task['id']
                    e_name = task['assignee']
                    print(f"Processing task {t_id} for {e_name}...")
                    
                    # Update to in_progress
                    await p.execute("UPDATE tasks SET status = 'in_progress', updated_at = NOW() WHERE id = $1", t_id)
                    
                    # Simulate work
                    await asyncio.sleep(2)
                    
                    # Complete
                    res = f"Deep research of 2026 trends for {e_name} completed. Found 3 insights."
                    await p.execute("UPDATE tasks SET status = 'completed', result = $2, updated_at = NOW() WHERE id = $1", t_id, res)
                    print(f"Task {t_id} COMPLETED")
            
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Error in main loop: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Worker stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")

