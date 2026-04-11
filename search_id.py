import asyncio
import asyncpg

async def search_id():
    try:
        conn = await asyncpg.connect('postgresql://admin:secret@localhost:6432/knowledge_os')
        target_id = 'd8707d50-8c08-464f-9aed-265bebf5375e'
        
        print(f"Searching for ID: {target_id}")
        
        # Search in tasks
        task = await conn.fetchrow('SELECT id, status FROM tasks WHERE id::text = $1', target_id)
        if task:
            print(f"Found in tasks: {task['status']}")
        
        # Search in interaction_logs
        log = await conn.fetchrow('SELECT id FROM interaction_logs WHERE id::text = $1', target_id)
        if log:
            print(f"Found in interaction_logs: {log['id']}")
            
        # Search in strategy_sessions
        session = await conn.fetchrow('SELECT id, status FROM strategy_sessions WHERE id::text = $1', target_id)
        if session:
            print(f"Found in strategy_sessions: {session['status']}")
            
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(search_id())
