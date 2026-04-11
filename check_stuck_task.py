import asyncio
import asyncpg

async def check_task():
    try:
        conn = await asyncpg.connect('postgresql://admin:secret@localhost:6432/knowledge_os')
        task = await conn.fetchrow('SELECT * FROM tasks WHERE id = $1', 'd8707d50-8c08-464f-9aed-265bebf5375e')
        if task:
            print(f"ID: {task['id']}")
            print(f"Title: {task['title']}")
            print(f"Status: {task['status']}")
            print(f"Created At: {task['created_at']}")
            print(f"Updated At: {task['updated_at']}")
            print(f"Result: {str(task['result'])[:200]}...")
        else:
            print('Task not found')
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_task())
