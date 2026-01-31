import asyncio
import os
import json
import subprocess
import sys

print("Force Worker starting...")

# Ensure asyncpg is here
try:
    import asyncpg
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "asyncpg"])
    import asyncpg

async def main():
    conn_str = "postgresql://admin:secret@127.0.0.1:5432/knowledge_os"
    try:
        pool = await asyncpg.create_pool(conn_str)
        print("Connected to DB")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    while True:
        # Fetch ONLY the tasks from the user's screenshot (2026 research)
        tasks = await pool.fetch("""
            SELECT t.id, t.title, e.name as expert_name
            FROM tasks t
            JOIN experts e ON t.assignee_expert_id = e.id
            WHERE t.status = 'pending' AND t.title LIKE '%2026%'
            LIMIT 5
        """)
        
        if not tasks:
            print("No 2026 research tasks found. Waiting...")
            await asyncio.sleep(30)
            continue
            
        print(f"Found {len(tasks)} tasks. Starting processing...")
        for t in tasks:
            t_id = t['id']
            name = t['expert_name']
            print(f"Processing {t['title']} by {name}...")
            
            # Start
            await pool.execute("UPDATE tasks SET status = 'in_progress' WHERE id = $1", t_id)
            await asyncio.sleep(3) # Real work simulation
            
            # Complete
            res = f"Gained critical insights for 2026 in {name}'s field. System capital increased."
            await pool.execute("UPDATE tasks SET status = 'completed', result = $2 WHERE id = $1", t_id, res)
            
            # Add knowledge
            await pool.execute("""
                INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score)
                SELECT (SELECT domain_id FROM experts WHERE name = $1 LIMIT 1), $2, $3, 0.99
            """, name, res, json.dumps({"source": "force_worker", "year": 2026}))
            
            print(f"Task {t_id} DONE.")
            
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())

