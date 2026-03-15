import asyncio
import logging
import random
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AgentChaosInjector:
    """
    [SINGULARITY 21.21] Chaos Monkey for AI Agents.
    Injects synthetic failures into Shadow Execution to test system resilience.
    """

    def __init__(self, failure_rate: float = 0.1):
        self.failure_rate = failure_rate

    async def apply_chaos(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Potentially mutates the context or result to simulate failure."""
        if random.random() > self.failure_rate:
            return context

        chaos_type = random.choice(["latency", "hallucination", "tool_error"])
        logger.warning(f"🐒 [CHAOS] Injecting {chaos_type} into agent workflow...")

        if chaos_type == "latency":
            await asyncio.sleep(random.uniform(5.0, 15.0))
        elif chaos_type == "hallucination":
            context["synthetic_hallucination"] = True
            context["result"] = "ERROR: Simulated AI Hallucination"
        elif chaos_type == "tool_error":
            context["tool_access_blocked"] = True

        return context


_chaos_injector = None


def get_chaos_injector():
    global _chaos_injector
    if _chaos_injector is None:
        _chaos_injector = AgentChaosInjector()
    return _chaos_injector
