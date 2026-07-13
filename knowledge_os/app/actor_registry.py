import json
import logging
import os
from typing import Any, Dict, Optional

try:
    from app.redis_manager import get_redis_manager
except ImportError:
    from redis_manager import get_redis_manager

logger = logging.getLogger("ActorRegistry")


class ActorRegistry:
    """
    [SINGULARITY 28.0] Global Actor Registry.
    Tracks active actors across the cluster using Redis.
    Expert Name -> {container_id, pid, state_link, last_seen}
    """

    def __init__(self):
        self.redis = get_redis_manager()
        self.key_prefix = "actor_registry:"

    async def register_actor(self, expert_name: str, metadata: Dict[str, Any]):
        """Register or update an actor in the registry."""
        key = f"{self.key_prefix}{expert_name}"
        metadata["last_seen"] = os.popen("date -u +%Y-%m-%dT%H:%M:%SZ").read().strip()
        await self.redis.set(key, json.dumps(metadata), expire=3600)  # 1 hour TTL
        logger.info(f"🧬 [REGISTRY] Actor {expert_name} registered: {metadata}")

    async def get_actor(self, expert_name: str) -> Optional[Dict[str, Any]]:
        """Get actor metadata from the registry."""
        key = f"{self.key_prefix}{expert_name}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def unregister_actor(self, expert_name: str):
        """Remove an actor from the registry."""
        key = f"{self.key_prefix}{expert_name}"
        await self.redis.delete(key)
        logger.info(f"🧬 [REGISTRY] Actor {expert_name} unregistered.")

    async def list_actors(self) -> Dict[str, Any]:
        """List all registered actors."""
        # Note: This is an expensive operation in Redis, use with caution
        keys = await self.redis.client.keys(f"{self.key_prefix}*")
        actors = {}
        for key in keys:
            name = key.decode().replace(self.key_prefix, "")
            data = await self.redis.get(key.decode())
            if data:
                actors[name] = json.loads(data)
        return actors


_registry = None


def get_actor_registry() -> ActorRegistry:
    global _registry
    if _registry is None:
        _registry = ActorRegistry()
    return _registry
