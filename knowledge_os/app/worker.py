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
    print("Installing asyncpg...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "asyncpg"])
    import asyncpg
# ------------------------------

# Database connection pool
pool = None

async def get_pool():
    global pool
    if pool is None:
        db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
        pool = await asyncpg.create_pool(
            db_url,
            min_size=2,
            max_size=5
        )
    return pool

async def process_task(task):
    pool = await get_pool()
    task_id = task['id']
    expert_name = task['assignee']
    
    print(f"[{datetime.now()}] Expert {expert_name} starting task: {task['title']}")
    
    # Update status to in_progress
    await pool.execute("UPDATE tasks SET status = 'in_progress', updated_at = NOW() WHERE id = $1", task_id)
    
    # Simulate thinking/work
    await asyncio.sleep(5)
    
    # Mark as completed (simple simulation for test)
    result = f"Research completed by {expert_name}. Identified 3 breakthrough insights for 2026."
    await pool.execute("UPDATE tasks SET status = 'completed', result = $2, updated_at = NOW() WHERE id = $1", task_id, result)
    
    # Log to knowledge_nodes
    await pool.execute("""
        INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, source_ref)
        SELECT (SELECT domain_id FROM experts WHERE name = $1 LIMIT 1), $2, $3, 0.9, 'autonomous_worker'
    """, expert_name, result, json.dumps({"task_id": str(task_id), "expert": expert_name}))
    
    print(f"[{datetime.now()}] Task {task_id} completed by {expert_name}")

async def main():
    print(f"[{datetime.now()}] Smart Worker v2.0 (Self-Healing) started...")
    while True:
        try:
            pool = await get_pool()
            # Find pending tasks with assignee name
            tasks = await pool.fetch("""
                SELECT t.id, t.title, t.description, e.name as assignee 
                FROM tasks t 
                JOIN experts e ON t.assignee_expert_id = e.id 
                WHERE t.status = 'pending' 
                ORDER BY t.created_at ASC LIMIT 5
            """)
            
            if tasks:
                print(f"Found {len(tasks)} pending tasks. Processing...")
                for task in tasks:
                    await process_task(task)
            
            await asyncio.sleep(10)
        except Exception as e:
            print(f"Worker loop error: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
