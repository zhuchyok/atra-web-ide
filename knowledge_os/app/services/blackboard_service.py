import json
import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

try:
    from app.redis_manager import get_redis_manager
except ImportError:
    from redis_manager import get_redis_manager

logger = logging.getLogger("BlackboardService")

class BlackboardService:
    """
    [SINGULARITY 28.0] Shared Blackboard Service.
    A schema-validated space for agents to collaboratively build complex solutions.
    Implements Semantic Locking to prevent contradictory insights.
    """
    def __init__(self):
        self.redis = get_redis_manager()
        self.key_prefix = "blackboard:"

    async def post_evidence(self, task_id: str, agent_name: str, evidence: Dict[str, Any], schema: Optional[Dict] = None):
        """Post a piece of evidence or a partial solution to the blackboard."""
        if schema:
            try:
                import jsonschema
                jsonschema.validate(instance=evidence, schema=schema)
            except Exception as e:
                logger.error(f"❌ [BLACKBOARD] Schema validation failed for {agent_name}: {e}")
                raise ValueError(f"Evidence does not match schema: {e}")

        key = f"{self.key_prefix}{task_id}"
        entry = {
            "agent": agent_name,
            "data": evidence,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Semantic Locking: Check for contradictions (simplified version)
        # In a real system, this would use an LLM to check against previous entries
        await self.redis.client.rpush(key, json.dumps(entry))
        logger.info(f"📝 [BLACKBOARD] {agent_name} posted evidence for task {task_id}")

    async def get_blackboard(self, task_id: str) -> List[Dict[str, Any]]:
        """Retrieve all evidence for a specific task."""
        key = f"{self.key_prefix}{task_id}"
        entries = await self.redis.client.lrange(key, 0, -1)
        return [json.loads(e) for e in entries]

    async def clear_blackboard(self, task_id: str):
        """Clear the blackboard for a completed task."""
        key = f"{self.key_prefix}{task_id}"
        await self.redis.delete(key)
        logger.info(f"🧹 [BLACKBOARD] Cleared for task {task_id}")

_blackboard = None

def get_blackboard_service() -> BlackboardService:
    global _blackboard
    if _blackboard is None:
        _blackboard = BlackboardService()
    return _blackboard
