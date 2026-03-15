import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

# Add parent dir to path to import app
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from app.event_bus import Event, EventType, get_event_bus
from app.victoria_event_handlers import VictoriaEventHandlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_self_healing")


async def simulate_error():
    """Simulate a LOG_ERROR_DETECTED event and verify the handler creates a task."""
    bus = get_event_bus()

    # Initialize handlers and subscribe them manually for the test
    handlers = VictoriaEventHandlers()
    bus.subscribe(EventType.LOG_ERROR_DETECTED, handlers.handle_log_error_detected)

    # Start the bus
    await bus.start()

    # Error info that looks like a real traceback
    error_info = {
        "container": "backend",
        "message": "ZeroDivisionError: division by zero",
        "file": "../backend/app/routers/chat.py",
        "line": 42,
        "context": '  File "backend/app/routers/chat.py", line 42, in stream_chat\n    result = 1 / 0',
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    event = Event(
        event_id=str(uuid.uuid4()),
        event_type=EventType.LOG_ERROR_DETECTED,
        payload={"error_info": error_info},
        source="test_monitor",
    )

    logger.info("📢 Publishing simulated LOG_ERROR_DETECTED event...")
    await bus.publish(event)

    # Wait for processing
    logger.info("⏳ Waiting for event processing (60s)...")
    await asyncio.sleep(60)

    # Verify task in DB
    try:
        import asyncpg

        db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
        conn = await asyncpg.connect(db_url)
        try:
            row = await conn.fetchrow(
                "SELECT id, title, status FROM tasks WHERE metadata->>'source' = 'self_healing_logs' ORDER BY created_at DESC LIMIT 1"
            )
            if row:
                logger.info(
                    f"✅ Task found in DB: ID={row['id']}, Title='{row['title']}', Status='{row['status']}'"
                )
                if row["status"] == "awaiting_approval":
                    logger.info("✅ SUCCESS: Task is in 'awaiting_approval' status.")
                else:
                    logger.error(
                        f"❌ FAILURE: Task status is '{row['status']}', expected 'awaiting_approval'."
                    )
            else:
                logger.error("❌ FAILURE: No task found in DB for self_healing_logs.")
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"❌ Error verifying DB: {e}")

    await bus.stop()


if __name__ == "__main__":
    asyncio.run(simulate_error())
