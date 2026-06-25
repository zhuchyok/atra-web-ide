import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict, Optional

try:
    from app.event_bus import Event, EventBus, EventType
except ImportError:
    from event_bus import Event, EventBus, EventType
from redis_manager import redis_manager

logger = logging.getLogger(__name__)


class EventBusRedisBridge:
    """
    Bridge between in-memory EventBus and Redis Streams for cross-process communication.
    """

    def __init__(self, event_bus: EventBus, stream_name: str = "event_bus_stream"):
        self.event_bus = event_bus
        self.stream_name = stream_name
        self.running = False
        self._consumer_task: Optional[asyncio.Task] = None
        self.consumer_name = f"bridge_{uuid.uuid4().hex[:8]}"
        self.group_name = "event_bus_group"
        # [SINGULARITY 24.3] Use global redis_manager
        self.redis_manager = redis_manager
        # Safety knobs for stale group cleanup.
        self.stale_group_idle_ms = int(
            os.getenv("REDIS_BRIDGE_STALE_GROUP_IDLE_MS", "21600000")
        )  # 6h
        self.stale_group_prune_limit = int(os.getenv("REDIS_BRIDGE_STALE_GROUP_PRUNE_LIMIT", "200"))

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    async def _cleanup_stale_groups(self, client, stream_key: str) -> int:
        """
        Best-effort cleanup of orphaned Redis stream consumer groups.
        A group is considered stale when:
          - it has no pending messages, and
          - it has no consumers OR all consumers have idle >= configured threshold.
        """
        removed = 0
        try:
            groups = await client.xinfo_groups(stream_key)
        except Exception as e:
            logger.debug(f"[BRIDGE] stale cleanup skipped: {e}")
            return 0

        for group in groups or []:
            if removed >= self.stale_group_prune_limit:
                break

            name = group.get("name")
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="ignore")
            if not name or not str(name).startswith("group_"):
                continue

            # Never delete current active bridge group.
            if str(name) == self.group_name:
                continue

            pending = self._safe_int(group.get("pending"), 0)
            if pending > 0:
                continue

            try:
                consumers = await client.xinfo_consumers(stream_key, str(name))
            except Exception:
                consumers = []

            is_stale = False
            if not consumers:
                is_stale = True
            else:
                idle_values = [
                    self._safe_int(c.get("idle"), 0) for c in consumers if isinstance(c, dict)
                ]
                if idle_values and all(idle >= self.stale_group_idle_ms for idle in idle_values):
                    is_stale = True

            if not is_stale:
                continue

            try:
                await client.xgroup_destroy(stream_key, str(name))
                removed += 1
            except Exception as e:
                logger.debug(f"[BRIDGE] stale group destroy failed for {name}: {e}")

        if removed > 0:
            logger.info(
                f"🧹 [BRIDGE] removed stale groups: {removed} (idle_ms>={self.stale_group_idle_ms}, limit={self.stale_group_prune_limit})"
            )
        return removed

    async def start(self):
        """Start the bridge"""
        if self.running:
            return

        logger.info(f"🌉 [BRIDGE] Starting Redis Bridge on stream {self.stream_name}...")
        self.running = True

        # [SINGULARITY 24.3] Fix: Each instance MUST have a unique group to receive all events
        # If multiple bridges use the same group, they will split the messages (load balance).
        # For a true bridge where EVERY process sees EVERY message, each process needs its own group.
        if not hasattr(self, "_group_created"):
            self.group_name = f"group_{uuid.uuid4().hex[:8]}"
            try:
                client = await self.redis_manager.get_client()
                stream_key = f"stream:{self.stream_name}"
                # Best-effort pre-cleanup to avoid unbounded group cardinality growth.
                await self._cleanup_stale_groups(client, stream_key)
                await client.xgroup_create(stream_key, self.group_name, id="$", mkstream=True)
                self._group_created = True
                logger.info(f"✅ [BRIDGE] Created unique consumer group: {self.group_name}")
            except Exception as e:
                logger.debug(f"Group creation: {e}")

        # 2. Subscribe to local events to publish them to Redis
        # We only publish events that are NOT from the bridge itself to avoid loops
        logger.info("🌉 [BRIDGE] Subscribing to local events...")
        for event_type in EventType:
            if event_type != EventType.REDIS_BRIDGE_SYNC:
                self.event_bus.subscribe(event_type, self._local_to_redis)

        # 3. Start Redis consumer
        logger.info("🌉 [BRIDGE] Starting consumer task...")
        self._consumer_task = asyncio.create_task(self._redis_to_local())
        logger.info(
            f"🌉 EventBus Redis Bridge started on stream {self.stream_name} (Group: {self.group_name})"
        )

    async def stop(self):
        """Stop the bridge and cleanup groups"""
        self.running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

        # [SINGULARITY 10.0] Cleanup stale consumer group
        if hasattr(self, "group_name") and self.group_name.startswith("group_"):
            try:
                client = await self.redis_manager.get_client()
                stream_key = f"stream:{self.stream_name}"
                await client.xgroup_destroy(stream_key, self.group_name)
                logger.info(f"🗑️ [BRIDGE] Destroyed stale consumer group: {self.group_name}")
            except Exception as e:
                logger.debug(f"Group destruction error: {e}")

        logger.info("🌉 EventBus Redis Bridge stopped")

    async def _local_to_redis(self, event: Event):
        """Publish local event to Redis"""
        if event.payload.get("_from_redis"):
            return  # Avoid loops

        # [SINGULARITY 24.3] DEBUG: Log local event being sent to Redis
        logger.info(
            f"📤 [BRIDGE] (PID: {os.getpid()}) Sending local event {event.event_type.value} to Redis stream {self.stream_name}"
        )

        # [SINGULARITY 24.3] Fix: Ensure payload is not modified in place to avoid side effects
        # if multiple handlers are processing the same event object.
        payload_copy = event.payload.copy()
        payload_copy["_from_redis"] = True

        data = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "payload": payload_copy,
            "source": event.source,
            "timestamp": event.timestamp.isoformat(),
            "correlation_id": event.correlation_id,
        }

        try:
            await self.redis_manager.push_to_stream(self.stream_name, data, deduplicate=False)
            logger.debug(f"✅ [BRIDGE] Event {event.event_id} pushed to Redis")
        except Exception as e:
            logger.error(f"❌ [BRIDGE] Failed to push event to Redis: {e}")

    async def _redis_to_local(self):
        """Consume events from Redis and publish them to local EventBus"""
        client = await self.redis_manager.get_client()
        logger.info(
            f"📥 [BRIDGE] Redis consumer loop started: {self.consumer_name} on group {self.group_name}"
        )

        while self.running:
            try:
                # Read from Redis Stream
                stream_key = f"stream:{self.stream_name}"

                # First, check for pending messages for ANY consumer in this group
                try:
                    pending_info = await client.xpending(stream_key, self.group_name)
                    if pending_info["pending"] > 0:
                        # Get pending messages
                        p_range = await client.xpending_range(
                            stream_key, self.group_name, "-", "+", 10
                        )
                        if p_range:
                            ids = [p["message_id"] for p in p_range]
                            logger.info(
                                f"📥 [BRIDGE] Claiming {len(ids)} pending messages for {self.consumer_name}"
                            )
                            await client.xclaim(
                                stream_key, self.group_name, self.consumer_name, 0, ids
                            )
                except Exception as e:
                    logger.debug(f"Pending check/claim error: {e}")

                # Now read from THIS consumer
                try:
                    messages = await client.xreadgroup(
                        self.group_name, self.consumer_name, {stream_key: ">"}, count=10, block=1000
                    )
                except Exception as e:
                    if "NOGROUP" in str(e):
                        logger.warning(
                            f"⚠️ [BRIDGE] Consumer group {self.group_name} missing. Recreating..."
                        )
                        try:
                            await client.xgroup_create(
                                stream_key, self.group_name, id="$", mkstream=True
                            )
                            continue  # Retry in next loop iteration
                        except Exception as re_e:
                            logger.error(f"❌ [BRIDGE] Failed to recreate group: {re_e}")
                    raise e

                if not messages:
                    # Fallback to reading pending messages if any
                    messages = await client.xreadgroup(
                        self.group_name, self.consumer_name, {stream_key: "0"}, count=10, block=100
                    )

                if not messages:
                    continue

                logger.info(
                    f"📥 [BRIDGE] Received {len(messages)} streams from Redis: {[s for s, m in messages]}"
                )
                for stream, msgs in messages:
                    logger.info(f"📥 [BRIDGE] Processing {len(msgs)} messages from stream {stream}")
                    for msg_id, data in msgs:
                        try:
                            raw_payload = data.get("payload")
                            if not raw_payload:
                                logger.warning(f"⚠️ [BRIDGE] No payload in message {msg_id}")
                                continue

                            if isinstance(raw_payload, str):
                                payload = json.loads(raw_payload)
                            else:
                                payload = raw_payload

                            # Reconstruct Event
                            # [SINGULARITY 24.3] Ensure payload is a dict
                            event_payload = payload.get("payload", {})
                            if not isinstance(event_payload, dict):
                                logger.warning(
                                    f"⚠️ [BRIDGE] Payload is not a dict: {type(event_payload)}"
                                )
                                event_payload = {"data": event_payload}

                            # Mark as from redis to avoid loops BEFORE publishing
                            event_payload["_from_redis"] = True

                            event = Event(
                                event_id=payload["event_id"],
                                event_type=EventType(payload["event_type"]),
                                payload=event_payload,
                                source=payload["source"],
                                correlation_id=payload.get("correlation_id"),
                            )

                            logger.info(
                                f"📥 [BRIDGE] Received event from Redis: {event.event_type.value} from {event.source}"
                            )

                            # [SINGULARITY 24.3] DEBUG: Log subscribers for this event type
                            handlers = self.event_bus.subscribers.get(event.event_type, [])
                            import os

                            logger.info(
                                f"📥 [BRIDGE] (PID: {os.getpid()}) Local EventBus (ID: {id(self.event_bus)}) has {len(handlers)} subscribers for {event.event_type.value}: {[h.__name__ for h in handlers]}"
                            )

                            # [SINGULARITY 24.3] DEBUG: If no subscribers, log ALL subscribers
                            if not handlers:
                                logger.info(
                                    f"🔍 [BRIDGE] ALL subscribers on this EventBus: {list(self.event_bus.subscribers.keys())}"
                                )

                            # Publish to local bus
                            try:
                                await self.event_bus.publish(event)
                            except Exception as pub_e:
                                logger.error(f"❌ [BRIDGE] Failed to publish to local bus: {pub_e}")

                            # Acknowledge
                            await client.xack(f"stream:{self.stream_name}", self.group_name, msg_id)

                        except Exception as e:
                            logger.error(f"❌ Bridge error processing message {msg_id}: {e}")

            except Exception as e:
                if self.running:
                    logger.error(f"⚠️ Bridge loop error: {e}")
                    await asyncio.sleep(5)


async def start_redis_bridge(event_bus: EventBus):
    bridge = EventBusRedisBridge(event_bus)
    await bridge.start()
    return bridge
