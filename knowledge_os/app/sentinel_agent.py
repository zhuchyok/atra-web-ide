import asyncio
import logging
import os
import time
from typing import Any, Dict

try:
    from app.codebase_mutation_engine import CodebaseMutationEngine
    from app.event_bus import Event, EventType, get_event_bus
except ImportError:
    from codebase_mutation_engine import CodebaseMutationEngine
    from event_bus import Event, EventType, get_event_bus

logger = logging.getLogger("SentinelAgent")


class SentinelAgent:
    """
    [SINGULARITY 10.0] Self-healing agent that reacts to system errors
    and service failures by attempting automated code or infra fixes.
    """

    def __init__(self):
        self.event_bus = get_event_bus()
        self.mutation_engine = CodebaseMutationEngine()
        self.running = False

    async def start(self):
        if self.running:
            return
        self.running = True

        # Subscribe to critical events
        self.event_bus.subscribe(EventType.SERVICE_DOWN, self.handle_service_failure)
        self.event_bus.subscribe(EventType.LOG_ERROR_DETECTED, self.handle_log_error)
        self.event_bus.subscribe(EventType.ACTION_REQUIRED, self.handle_action_request)

        logger.info("🛡️ [SENTINEL] Sentinel Agent is active and watching...")

    async def handle_service_failure(self, event: Event):
        service_name = event.payload.get("service_name")
        logger.warning(f"🛡️ [SENTINEL] Detected service failure: {service_name}")

        # Logic for specific services (e.g., if worker is down, check for syntax errors)
        if "worker" in service_name.lower():
            await self._check_and_fix_worker_syntax()

    async def handle_log_error(self, event: Event):
        error_text = event.payload.get("error", "")
        if "SyntaxError" in error_text or "IndentationError" in error_text:
            logger.warning("🛡️ [SENTINEL] Detected syntax error in logs. Triggering auto-fix...")
            # Extract file path from error_text if possible and call mutation engine
            # For now, we log and notify
            await self.event_bus.publish(
                Event(
                    event_id=f"sentinel_fix_{int(time.time())}",
                    event_type=EventType.ACTION_REQUIRED,
                    payload={"action": "fix_syntax", "details": error_text},
                    source="sentinel_agent",
                )
            )

    async def handle_action_request(self, event: Event):
        action = event.payload.get("action")
        logger.info(f"🛡️ [SENTINEL] Processing action request: {action}")
        # Implementation of specific healing actions

    async def _check_and_fix_worker_syntax(self):
        """Example: Check if the worker file has syntax errors and revert if needed."""
        worker_path = os.path.join(os.path.dirname(__file__), "smart_worker_autonomous.py")
        try:
            import py_compile

            py_compile.compile(worker_path, doraise=True)
            logger.info("🛡️ [SENTINEL] Worker syntax is OK.")
        except py_compile.PyCompileError:
            logger.error("🛡️ [SENTINEL] Worker syntax is BROKEN! Attempting rollback...")
            # Trigger rollback logic (e.g., from .bak file)
            from app.service_monitor import ServiceMonitor

            monitor = ServiceMonitor()
            await monitor.rollback_mutation("smart_worker_autonomous")


async def start_sentinel():
    sentinel = SentinelAgent()
    await sentinel.start()
    return sentinel
