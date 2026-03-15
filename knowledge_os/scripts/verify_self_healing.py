import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from app.event_bus import Event, EventType, get_event_bus
from app.victoria_event_handlers import VictoriaEventHandlers

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_self_healing")


async def verify_self_healing():
    """
    Verify the self-healing log monitoring flow:
    1. Manually publish a LOG_ERROR_DETECTED event.
    2. Check if the handler processes it and creates a task.
    """
    bus = get_event_bus()
    handlers = VictoriaEventHandlers()

    # Start the event bus
    await bus.start()

    # Subscribe the handler to the event bus
    bus.subscribe(EventType.LOG_ERROR_DETECTED, handlers.handle_log_error_detected)

    logger.info("🧪 [TEST] Simulating a log error event...")

    # Create a dummy file for the mutation engine to find
    test_file = "test_error_file.py"
    with open(test_file, "w") as f:
        f.write("def divide(a, b):\n    return a / b\n\ndivide(1, 0)\n")

    error_info = {
        "container": "test-container",
        "message": "ZeroDivisionError: division by zero",
        "file": os.path.abspath(test_file),
        "line": 2,
        "context": 'Traceback (most recent call last):\n  File "test_error_file.py", line 4, in <module>\n    divide(1, 0)\n  File "test_error_file.py", line 2, in divide\n    return a / b\nZeroDivisionError: division by zero',
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    event = Event(
        event_id=str(uuid.uuid4()),
        event_type=EventType.LOG_ERROR_DETECTED,
        payload={"error_info": error_info},
        source="test_verification_script",
    )

    # Publish the event
    await bus.publish(event)

    logger.info("⏳ [TEST] Waiting for handler to process event...")
    await asyncio.sleep(5)  # Wait for processing and potential Victoria call

    # Clean up test file
    if os.path.exists(test_file):
        os.remove(test_file)

    logger.info("✅ [TEST] Verification script finished. Check logs for task creation status.")
    await bus.stop()


if __name__ == "__main__":
    asyncio.run(verify_self_healing())
