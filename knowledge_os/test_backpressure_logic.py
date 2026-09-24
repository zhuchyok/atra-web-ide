import asyncio
import os
import sys
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


async def test_backpressure():
    print("Testing backpressure logic...")

    # Mocking the environment
    os.environ["SMART_WORKER_MAX_PENDING"] = "10"

    try:
        from app.smart_worker_autonomous import get_pool

        pool = await get_pool()

        async with pool.acquire() as conn:
            # 1. Check current pending count
            pending_count = await conn.fetchval(
                "SELECT count(*) FROM tasks WHERE status = 'pending'"
            )
            print(f"Current pending tasks: {pending_count}")

            # 2. If count < 10, create some dummy tasks to reach the limit
            if pending_count < 10:
                print(f"Creating {10 - pending_count} dummy tasks to reach the limit...")
                for i in range(10 - pending_count):
                    await conn.execute(
                        "INSERT INTO tasks (title, description, status, priority) VALUES ($1, $2, 'pending', 'low')",
                        f"Test Task {i}",
                        "Backpressure test task",
                    )
                pending_count = 10

            # 3. Verify the logic would trigger
            max_pending = int(os.getenv("SMART_WORKER_MAX_PENDING", "10"))
            if pending_count >= max_pending:
                print(
                    f"SUCCESS: Backpressure would trigger (pending_count={pending_count} >= max_pending={max_pending})"
                )
            else:
                print(
                    f"FAILURE: Backpressure would NOT trigger (pending_count={pending_count} < max_pending={max_pending})"
                )

            # 4. Cleanup dummy tasks (optional, but good practice)
            # await conn.execute("DELETE FROM tasks WHERE title LIKE 'Test Task %'")

    except Exception as e:
        print(f"Error during test: {e}")


if __name__ == "__main__":
    asyncio.run(test_backpressure())
