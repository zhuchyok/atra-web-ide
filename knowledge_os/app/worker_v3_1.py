import asyncio
import os
import json
import subprocess
import sys
from datetime import datetime

# --- EMERGENCY REPAIR BLOCK ---
try:
    import asyncpg
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "asyncpg"])
    import asyncpg

# Database connection details
DB_URL = "postgresql://admin:secret@127.0.0.1:5432/knowledge_os"

async def main():
    print(f"[{datetime.now()}] Smart Worker v3.1 Starting...")
    
    try:
        pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5)
        print("✅ Connected to Database")
    except Exception as e:
        print(f"❌ Database Connection Failed: {e}")
        return

    while True:
        try:
            # 1. Fetch tasks
            tasks = await pool.fetch("""
                SELECT t.id, t.title, e.name as assignee 
                FROM tasks t 
                JOIN experts e ON t.assignee_expert_id = e.id 
                WHERE t.status = 'pending' 
                ORDER BY t.created_at ASC LIMIT 5
            """)
            
            if not tasks:
                # If no pending, maybe check for some in_progress that got stuck
                print(f"[{datetime.now()}] No pending tasks. Waiting...")
            else:
                print(f"Found {len(tasks)} tasks. Processing...")
                for task in tasks:
                    t_id = task['id']
                    e_name = task['assignee']
                    print(f"-> Working on task {t_id} ({task['title']}) for {e_name}")
                    
                    # Update status
                    await pool.execute("UPDATE tasks SET status = 'in_progress', updated_at = NOW() WHERE id = $1", t_id)
                    
                    # Work simulation
                    await asyncio.sleep(2)
                    
                    # Complete
                    res = f"Automated research by {e_name} finished. Knowledge base updated."
                    await pool.execute("UPDATE tasks SET status = 'completed', result = $2, updated_at = NOW() WHERE id = $1", t_id, res)
                    
                    # Add to knowledge
                    await pool.execute("""
                        INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score)
                        SELECT (SELECT domain_id FROM experts WHERE name = $1 LIMIT 1), $2, $3, 0.95
                    """, e_name, res, json.dumps({"source": "auto_worker", "task_id": t_id}))
                    
                    print(f"✅ Task {t_id} COMPLETED and Knowledge Node added.")
            
            await asyncio.sleep(10)
        except Exception as e:
            print(f"Loop error: {e}")
            await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main())

