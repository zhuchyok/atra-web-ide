import asyncio
import os
import json
import subprocess
import sys
from datetime import datetime
import asyncpg

# Database connection pool
pool = None

async def get_pool():
    global pool
    if pool is None:
        db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
        pool = await asyncpg.create_pool(
            db_url, 
            min_size=1, 
            max_size=5,  # Уменьшено для предотвращения перегрузки БД
            max_inactive_connection_lifetime=300
        )
    return pool

def run_cursor_agent(prompt: str):
    try:
        env = os.environ.copy()
        print(f"[{datetime.now()}] Calling cursor-agent...")
        result = subprocess.run(
            ['/root/.local/bin/cursor-agent', '--print', prompt],
            capture_output=True, text=True, check=True, timeout=600, env=env
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"[{datetime.now()}] Agent error: {e}")
        return None

async def process_task(task):
    pool = await get_pool()
    task_id = task['id']
    expert_name = task['assignee']
    expert_prompt = task['system_prompt']
    
    print(f"[{datetime.now()}] >>> PROCESSING TASK: {task['title']} (Assignee: {expert_name})")
    await pool.execute("UPDATE tasks SET status = 'in_progress', updated_at = NOW() WHERE id = $1", task_id)
    
    prompt = f"{expert_prompt}\n\nЗАДАЧА: {task['title']}\nИНСТРУКЦИЯ: {task['description']}\n\nТВОЯ ЦЕЛЬ: Выполни задачу максимально глубоко и профессионально. Сформулируй 3-5 ключевых инсайтов или решений. Ответь в формате экспертного отчета."
    
    report = run_cursor_agent(prompt)
    
    if report:
        print(f"[{datetime.now()}] Task {task_id} report received. Saving...")
        await pool.execute("UPDATE tasks SET status = 'completed', result = $2, updated_at = NOW() WHERE id = $1", task_id, report)
        
        # Log to knowledge_nodes
        domain_id = await pool.fetchval("SELECT domain_id FROM experts WHERE name = $1 LIMIT 1", expert_name)
        await pool.execute("""
            INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, is_verified)
            VALUES ($1, $2, $3, 0.95, TRUE)
        """, domain_id, f"📊 ОТЧЕТ ЭКСПЕРТА ({expert_name}): {task['title']}\n\n{report}", 
        json.dumps({"task_id": str(task_id), "expert": expert_name, "source": "autonomous_worker"}))
        
        print(f"[{datetime.now()}] Task {task_id} SUCCESS.")
    else:
        await pool.execute("UPDATE tasks SET status = 'pending', updated_at = NOW() WHERE id = $1", task_id)
        print(f"[{datetime.now()}] Task {task_id} FAILED (empty response). Reverted to pending.")

async def main():
    print(f"[{datetime.now()}] --- Autonomous Smart Worker v3.1 started ---")
    while True:
        try:
            pool = await get_pool()
            # Find pending tasks
            tasks = await pool.fetch("""
                SELECT t.id, t.title, t.description, e.name as assignee, e.system_prompt 
                FROM tasks t 
                JOIN experts e ON t.assignee_expert_id = e.id 
                WHERE t.status = 'pending' 
                ORDER BY t.created_at ASC LIMIT 3
            """)
            
            if tasks:
                print(f"[{datetime.now()}] Found {len(tasks)} pending tasks.")
                for task in tasks:
                    await process_task(task)
            else:
                # No tasks found, check for stuck in_progress
                # (Optional: reset tasks that are in_progress for too long)
                pass
            
            await asyncio.sleep(10)
        except Exception as e:
            print(f"[{datetime.now()}] Global loop error: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())

