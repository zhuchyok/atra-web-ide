import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import docker
from app.event_bus import Event, EventType, get_event_bus

logger = logging.getLogger(__name__)


class LogMonitor:
    """
    Real-time log monitoring system for Docker containers.
    Detects Python Tracebacks and ERROR messages.
    """

    def __init__(self, containers: List[str] = None):
        self.container_names = containers or ["victoria-agent", "backend", "knowledge-os"]
        try:
            self.client = docker.from_env()
        except Exception as e:
            logger.error(f"❌ [LOG_MONITOR] Failed to connect to Docker: {e}")
            self.client = None

        self.event_bus = get_event_bus()
        self.running = False
        self._tasks = []

    async def start(self):
        """Start monitoring logs for all specified containers."""
        if not self.client:
            logger.error("❌ [LOG_MONITOR] Docker client not available. Monitoring aborted.")
            return

        self.running = True
        logger.info(
            f"🚀 [LOG_MONITOR] Starting log monitoring for: {', '.join(self.container_names)}"
        )

        for name in self.container_names:
            task = asyncio.create_task(self._monitor_container(name))
            self._tasks.append(task)

    async def stop(self):
        """Stop all monitoring tasks."""
        self.running = False
        for task in self._tasks:
            task.cancel()
        self._tasks = []
        logger.info("🛑 [LOG_MONITOR] Log monitoring stopped")

    async def _monitor_container(self, container_name: str):
        """Monitor logs for a single container."""
        while self.running:
            try:
                container = self.client.containers.get(container_name)
                logger.info(f"👀 [LOG_MONITOR] Tailing logs for {container_name}")

                # Using stream=True to tail logs efficiently
                for line in container.logs(stream=True, follow=True, tail=10):
                    if not self.running:
                        break

                    line_str = line.decode("utf-8", errors="replace").strip()
                    if not line_str:
                        continue

                    # Detect Python Traceback or ERROR level
                    if "Traceback (most recent call last):" in line_str or " ERROR " in line_str:
                        await self._handle_detected_error(container_name, line_str, container)

            except docker.errors.NotFound:
                logger.warning(
                    f"⚠️ [LOG_MONITOR] Container {container_name} not found. Retrying in 10s..."
                )
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"❌ [LOG_MONITOR] Error monitoring {container_name}: {e}")
                await asyncio.sleep(5)

    async def _handle_detected_error(self, container_name: str, initial_line: str, container):
        """Extract context and publish error event."""
        logger.warning(
            f"🚨 [LOG_MONITOR] Error detected in {container_name}: {initial_line[:100]}..."
        )

        # Extract context (20 lines)
        # Note: container.logs(tail=20) is an efficient way to get recent lines
        try:
            context_bytes = container.logs(tail=20)
            context = context_bytes.decode("utf-8", errors="replace")
        except:
            context = initial_line

        # Try to extract file and line from Traceback
        file_path = None
        line_number = None

        # Simple regex for Python traceback lines: File "path/to/file.py", line 123, in ...
        match = re.search(r'File "([^"]+)", line (\d+)', context)
        if match:
            file_path = match.group(1)
            line_number = int(match.group(2))

        error_info = {
            "container": container_name,
            "message": initial_line,
            "file": file_path,
            "line": line_number,
            "context": context,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.LOG_ERROR_DETECTED,
            payload={"error_info": error_info},
            source=f"log_monitor_{container_name}",
        )

        await self.event_bus.publish(event)


async def main():
    """Manual test for LogMonitor"""
    logging.basicConfig(level=logging.INFO)
    monitor = LogMonitor()
    await monitor.start()
    try:
        await asyncio.sleep(60)
    finally:
        await monitor.stop()


if __name__ == "__main__":
    asyncio.run(main())
