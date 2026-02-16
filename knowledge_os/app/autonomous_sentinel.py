"""
[SINGULARITY 12.0] Autonomous Sentinel.
Proactive background service for system maintenance, auto-remediation, and code guard.
Subscribes to EventBus and triggers autonomous actions based on system events.
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from event_bus import get_event_bus, Event, EventType

logger = logging.getLogger(__name__)

class AutonomousSentinel:
    """
    Proactive Autonomous Maintenance: The 'Guardian' of the corporation.
    """
    
    def __init__(self):
        self.bus = get_event_bus()
        self.is_running = False
        self._lock = asyncio.Lock()
        self.active_remediations = set()

    async def start(self):
        """Starts the Sentinel and subscribes to critical events."""
        async with self._lock:
            if self.is_running:
                return
            self.is_running = True
            
        # Subscribe to critical events
        self.bus.subscribe(EventType.SERVICE_DOWN, self.handle_service_down)
        self.bus.subscribe(EventType.ERROR_DETECTED, self.handle_error_detected)
        self.bus.subscribe(EventType.PERFORMANCE_DEGRADED, self.handle_performance_degraded)
        self.bus.subscribe(EventType.FILE_MODIFIED, self.handle_code_change)
        
        logger.info("🛡️ [SENTINEL] Autonomous Sentinel is active and guarding the system.")

    async def handle_service_down(self, event: Event):
        """Remediation for service failures."""
        service_name = event.payload.get("service_name", "unknown")
        if service_name in self.active_remediations:
            return
            
        self.active_remediations.add(service_name)
        logger.warning(f"🚨 [SENTINEL] Service {service_name} is DOWN. Triggering autonomous recovery...")
        
        try:
            # 1. Attempt auto-restart via SandboxManager/Docker
            from sandbox_manager import get_sandbox_manager
            sm = get_sandbox_manager()
            # Logic to find and restart container
            logger.info(f"🔄 [SENTINEL] Attempting to restart container for {service_name}")
            # sm.restart_container(service_name) # Placeholder for real restart logic
            
            # 2. Log to knowledge nodes
            from ai_core import run_smart_agent_async
            await run_smart_agent_async(
                f"Service {service_name} was down and I attempted recovery. Analyze the logs and suggest long-term fix.",
                expert_name="SRE",
                category="reasoning"
            )
        finally:
            self.active_remediations.remove(service_name)

    async def handle_error_detected(self, event: Event):
        """Remediation for system errors."""
        error_msg = event.payload.get("error", "")
        logger.error(f"🚨 [SENTINEL] Error detected: {error_msg[:100]}...")
        
        # Trigger Autonomous Tool Creator if it looks like a missing capability
        if "not found" in error_msg.lower() or "no such" in error_msg.lower():
            from autonomous_tool_creator import get_autonomous_tool_creator
            creator = get_autonomous_tool_creator()
            asyncio.create_task(creator.create_tool_on_the_fly(error_msg, "System Maintenance"))

    async def handle_performance_degraded(self, event: Event):
        """Optimization for performance issues."""
        component = event.payload.get("component", "unknown")
        logger.warning(f"📉 [SENTINEL] Performance degraded in {component}. Triggering optimization...")
        
        if component == "knowledge_graph":
            from graph_optimizer import run_optimization_cycle
            asyncio.create_task(run_optimization_cycle())

    async def handle_code_change(self, event: Event):
        """Proactive Code Guard: Check modified files for issues."""
        file_path = event.payload.get("file_path", "")
        if not file_path.endswith(".py"):
            return
            
        logger.info(f"🔍 [SENTINEL] Code Guard: Scanning modified file {file_path}")
        
        # Run autonomous audit
        audit_prompt = f"""
        Analyze the changes in {file_path}. 
        Check for:
        1. Syntax errors
        2. Security vulnerabilities
        3. Performance bottlenecks
        
        If you find critical issues, provide a fix.
        """
        try:
            from ai_core import run_smart_agent_async
            analysis = await run_smart_agent_async(audit_prompt, expert_name="Security", category="coding")
            if "FIX NEEDED" in analysis:
                logger.warning(f"⚠️ [SENTINEL] Code Guard found issues in {file_path}. Creating autonomous fix...")
                # Logic to apply fix via apply_patch
        except Exception:
            pass

_instance = None
def get_autonomous_sentinel():
    global _instance
    if _instance is None:
        _instance = AutonomousSentinel()
    return _instance
