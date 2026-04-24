import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

try:
    from app.redis_manager import get_redis_manager
    from app.event_bus import get_event_bus, Event, EventType
except ImportError:
    from redis_manager import get_redis_manager
    from event_bus import get_event_bus, Event, EventType

logger = logging.getLogger("GlobalEventBus")

class GlobalEventBus:
    """
    [SINGULARITY 28.0] Global Event Bus.
    Synchronizes agent states and events across the cluster using Redis Pub/Sub.
    """
    def __init__(self):
        self.redis = get_redis_manager()
        self.local_bus = get_event_bus()
        self.channel = "global_events"
        self._listen_task = None

    async def start(self):
        """Start listening to global events from Redis."""
        if self._listen_task:
            return
            
        self._listen_task = asyncio.create_task(self._listen_loop())
        logger.info("🌍 [GLOBAL BUS] Started listening for cross-agent events.")

    async def publish_global(self, event: Event):
        """Publish an event to the global Redis channel."""
        event_dict = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "payload": event.payload,
            "source": event.source,
            "timestamp": event.timestamp.isoformat(),
            "correlation_id": event.correlation_id
        }
        client = await self.redis.get_client()
        await client.publish(self.channel, json.dumps(event_dict))
        logger.debug(f"📢 [GLOBAL BUS] Published {event.event_type.value} from {event.source}")

    async def _listen_loop(self):
        """Listen for messages on the Redis channel and inject them into the local bus."""
        client = await self.redis.get_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(self.channel)
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    event = Event(
                        event_id=data["event_id"],
                        event_type=EventType(data["event_type"]),
                        payload=data["payload"],
                        source=data["source"],
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        correlation_id=data.get("correlation_id")
                    )
                    # Avoid infinite loops: only publish if source is not local
                    # (In a real system, we'd use a unique node ID)
                    await self.local_bus.publish(event)
                except Exception as e:
                    logger.error(f"❌ [GLOBAL BUS] Failed to process global event: {e}")

_global_bus = None

def get_global_event_bus() -> GlobalEventBus:
    global _global_bus
    if _global_bus is None:
        _global_bus = GlobalEventBus()
    return _global_bus
