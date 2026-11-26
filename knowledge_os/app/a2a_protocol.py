"""
Google Agent-to-Agent (A2A) Protocol Compliance Layer

Implements A2A data models, agent card discovery, task management,
and bidirectional mapping between A2A and the existing µACP agent messaging.

Specification: https://developers.google.com/a2a
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://host.docker.internal:6379/0")
A2A_CARD_TTL = int(os.getenv("A2A_CARD_TTL", "3600"))
A2A_TASK_TTL = int(os.getenv("A2A_TASK_TTL", "86400"))


class A2ATaskState(str, Enum):
    """A2A task lifecycle states per Google A2A spec."""

    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input_required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class A2AMessage:
    """A structured message between agents (A2A spec)."""

    role: str  # "user" | "agent"
    content: List[Dict[str, Any]]  # parts: [{"type":"text","text":"..."}, {"type":"file","file":{...}}]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "A2AMessage":
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AgentCard:
    """Agent advertisement card (A2A Agent Card spec)."""

    name: str
    description: str
    url: str
    skills: List[str]
    authentication: Dict[str, str]
    version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "skills": self.skills,
            "authentication": self.authentication,
            "version": self.version,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentCard":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            url=data.get("url", ""),
            skills=data.get("skills", []),
            authentication=data.get("authentication", {}),
            version=data.get("version", "1.0"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class A2ATask:
    """Unit of work in the A2A protocol."""

    task_id: str
    state: A2ATaskState
    messages: List[A2AMessage]
    agent_card: AgentCard
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "state": self.state.value,
            "messages": [m.to_dict() for m in self.messages],
            "agent_card": self.agent_card.to_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "A2ATask":
        return cls(
            task_id=data.get("task_id", str(uuid.uuid4())),
            state=A2ATaskState(data.get("state", "submitted")),
            messages=[A2AMessage.from_dict(m) for m in data.get("messages", [])],
            agent_card=AgentCard.from_dict(data.get("agent_card", {})),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if "updated_at" in data
            else datetime.now(timezone.utc),
            metadata=data.get("metadata", {}),
        )


class A2AProtocolAdapter:
    """
    A2A Protocol compliance adapter for the ATRA multi-agent system.

    Bridges Google's A2A protocol with the existing μACP messaging layer.
    """

    def __init__(self):
        self._cards: Dict[str, AgentCard] = {}
        self._tasks: Dict[str, A2ATask] = {}
        self._redis = None

    # ── Redis helpers ──────────────────────────────────────────────────────

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(REDIS_URL, decode_responses=True)
            except ImportError:
                logger.warning("[A2A] redis.asyncio not available, using in-memory only")
                return None
        return self._redis

    async def close(self):
        """Close Redis connection."""
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None

    # ── Registry ───────────────────────────────────────────────────────────

    def register_agent(self, card: AgentCard):
        """Register an agent's A2A card in memory."""
        self._cards[card.name] = card
        logger.info(f"[A2A] Agent card registered: {card.name} ({len(card.skills)} skills)")

    async def persist_card(self, card: AgentCard):
        """Persist agent card to Redis for cross-process discovery (best-effort)."""
        r = await self._get_redis()
        if not r:
            return
        try:
            key = f"a2a:card:{card.name}"
            await r.setex(key, A2A_CARD_TTL, json.dumps(card.to_dict(), ensure_ascii=False))
        except Exception as e:
            logger.debug(f"[A2A] Failed to persist card for {card.name}: {e}")

    def discover_agents(self) -> List[AgentCard]:
        """Get all registered agent cards from memory."""
        return list(self._cards.values())

    async def discover_agents_redis(self) -> List[AgentCard]:
        """Discover all agents from Redis (cross-process)."""
        r = await self._get_redis()
        if not r:
            return list(self._cards.values())
        cards = []
        try:
            keys = await r.keys("a2a:card:*")
            for key in keys:
                raw = await r.get(key)
                if raw:
                    cards.append(AgentCard.from_dict(json.loads(raw)))
        except Exception as e:
            logger.debug(f"[A2A] Redis discovery failed: {e}")
        return cards

    def discover_agent(self, name: str) -> Optional[AgentCard]:
        """Get a specific agent's card from memory."""
        return self._cards.get(name)

    async def get_card_for_agent(self, agent_name: str) -> AgentCard:
        """Generate or retrieve an AgentCard for a named agent.

        First checks in-memory registry, then Redis, then DB.
        Falls back to generating a card from experts table data.
        """
        card = self._cards.get(agent_name)
        if card:
            return card

        r = await self._get_redis()
        if r:
            try:
                raw = await r.get(f"a2a:card:{agent_name}")
                if raw:
                    card = AgentCard.from_dict(json.loads(raw))
                    self._cards[agent_name] = card
                    return card
            except Exception:
                pass

        card = await self._generate_card_from_db(agent_name)
        if card:
            self._cards[agent_name] = card
            return card

        return AgentCard(
            name=agent_name,
            description=f"Agent {agent_name}",
            url=self.generate_card_url(agent_name),
            skills=[],
            authentication={},
        )

    async def _generate_card_from_db(self, agent_name: str) -> Optional[AgentCard]:
        """Query the experts table and build an AgentCard."""
        try:
            try:
                from app.db_pool import get_pool
            except ImportError:
                from db_pool import get_pool

            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT name, role, department, system_prompt, metadata FROM experts WHERE name = $1",
                    agent_name,
                )
                if not row:
                    return None

                name = row["name"]
                role = row.get("role") or ""
                department = row.get("department") or ""
                system_prompt = row.get("system_prompt") or ""
                meta = row.get("metadata") or {}

                skills = []
                if role:
                    skills.append(role)
                if department:
                    skills.append(department)
                if isinstance(meta, dict):
                    extra = meta.get("skills") or meta.get("capabilities") or []
                    if isinstance(extra, list):
                        skills.extend(extra)

                return AgentCard(
                    name=name,
                    description=system_prompt[:200] if system_prompt else f"Expert: {name}",
                    url=self.generate_card_url(name),
                    skills=skills,
                    authentication={},
                    metadata={
                        "role": role,
                        "department": department,
                        "source": "experts_table",
                    },
                )
        except Exception as e:
            logger.warning(f"[A2A] Failed to generate card from DB for {agent_name}: {e}")
            return None

    def generate_card_url(self, agent_name: str) -> str:
        """Generate the A2A endpoint URL for an agent."""
        safe_name = agent_name.lower().replace(" ", "-").replace("_", "-")
        return f"/a2a/agents/{safe_name}"

    # ── Task management ────────────────────────────────────────────────────

    async def send_task(self, target_agent: str, task: A2ATask) -> A2ATask:
        """Send an A2A task to another agent via existing agent_messaging.

        1. Convert A2ATask -> AgentMessage (verb="ASK")
        2. Send via send_message()
        3. Wait for response (poll or use correlation_id)
        4. Convert response back to A2ATask
        5. Return updated task
        """
        try:
            from app.agent_messaging import send_message
        except ImportError:
            from agent_messaging import send_message

        msg_dict = self.to_agent_message(task)
        correlation_id = task.task_id

        msg_id = await send_message(
            from_agent=task.agent_card.name,
            to_agent=target_agent,
            verb="ASK",
            payload=msg_dict,
            correlation_id=correlation_id,
            requires_response=True,
        )

        if not msg_id:
            task.state = A2ATaskState.FAILED
            task.updated_at = datetime.now(timezone.utc)
            await self._persist_task(task)
            return task

        task.state = A2ATaskState.WORKING
        task.updated_at = datetime.now(timezone.utc)
        await self._persist_task(task)

        self._tasks[task.task_id] = task

        response_payload = await self._poll_for_response(correlation_id, target_agent)
        if response_payload is None:
            task.state = A2ATaskState.FAILED
            task.messages.append(
                A2AMessage(
                    role="agent",
                    content=[{"type": "text", "text": "No response received from target agent"}],
                )
            )
        else:
            try:
                response_task = self.from_agent_message(response_payload)
                task.state = response_task.state
                task.messages.extend(response_task.messages)
            except Exception:
                task.state = A2ATaskState.COMPLETED
                task.messages.append(
                    A2AMessage(
                        role="agent",
                        content=[{"type": "text", "text": json.dumps(response_payload, ensure_ascii=False)}],
                    )
                )

        task.updated_at = datetime.now(timezone.utc)
        await self._persist_task(task)
        return task

    async def _poll_for_response(self, correlation_id: str, target_agent: str, timeout: float = 30.0) -> Optional[Dict]:
        """Poll Redis for a response message with the matching correlation_id."""
        r = await self._get_redis()
        if not r:
            return None

        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                raw = await r.get(f"a2a:response:{correlation_id}")
                if raw:
                    await r.delete(f"a2a:response:{correlation_id}")
                    return json.loads(raw)
            except Exception:
                pass
            await asyncio.sleep(0.5)

        logger.warning(f"[A2A] Poll timeout for correlation_id={correlation_id}")
        return None

    async def get_task_status(self, task_id: str) -> Optional[A2ATaskState]:
        """Check task status from Redis."""
        if task_id in self._tasks:
            return self._tasks[task_id].state

        r = await self._get_redis()
        if not r:
            return None

        try:
            raw = await r.get(f"a2a:task:{task_id}")
            if raw:
                task = A2ATask.from_dict(json.loads(raw))
                self._tasks[task_id] = task
                return task.state
        except Exception:
            pass
        return None

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        task = self._tasks.get(task_id)
        if task:
            if task.state in (A2ATaskState.COMPLETED, A2ATaskState.FAILED, A2ATaskState.CANCELED):
                return False
            task.state = A2ATaskState.CANCELED
            task.updated_at = datetime.now(timezone.utc)
            await self._persist_task(task)
            return True

        r = await self._get_redis()
        if not r:
            return False

        try:
            raw = await r.get(f"a2a:task:{task_id}")
            if raw:
                task = A2ATask.from_dict(json.loads(raw))
                if task.state in (A2ATaskState.COMPLETED, A2ATaskState.FAILED, A2ATaskState.CANCELED):
                    return False
                task.state = A2ATaskState.CANCELED
                task.updated_at = datetime.now(timezone.utc)
                await r.setex(
                    f"a2a:task:{task_id}",
                    A2A_TASK_TTL,
                    json.dumps(task.to_dict(), ensure_ascii=False),
                )
                self._tasks[task_id] = task
                return True
        except Exception:
            pass
        return False

    async def _persist_task(self, task: A2ATask):
        """Persist task state to Redis."""
        self._tasks[task.task_id] = task
        r = await self._get_redis()
        if not r:
            return
        try:
            await r.setex(
                f"a2a:task:{task.task_id}",
                A2A_TASK_TTL,
                json.dumps(task.to_dict(), ensure_ascii=False),
            )
        except Exception as e:
            logger.debug(f"[A2A] Failed to persist task {task.task_id}: {e}")

    # ── Protocol mapping ───────────────────────────────────────────────────

    def to_agent_message(self, task: A2ATask) -> dict:
        """Convert A2ATask -> AgentMessage-compatible dict (for agent_messaging.send_message)."""
        return {
            "a2a_version": "1.0",
            "task_id": task.task_id,
            "state": task.state.value,
            "messages": [m.to_dict() for m in task.messages],
            "agent_card": task.agent_card.to_dict(),
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "metadata": task.metadata,
        }

    def from_agent_message(self, msg: dict) -> A2ATask:
        """Convert AgentMessage payload dict -> A2ATask."""
        task_id = msg.get("task_id", str(uuid.uuid4()))
        messages_raw = msg.get("messages", [])
        messages = [A2AMessage.from_dict(m) if isinstance(m, dict) else A2AMessage(role="agent", content=[{"type": "text", "text": str(m)}]) for m in messages_raw]

        card_raw = msg.get("agent_card", {})
        card = AgentCard.from_dict(card_raw) if isinstance(card_raw, dict) else AgentCard(name="unknown", description="", url="", skills=[], authentication={})

        return A2ATask(
            task_id=task_id,
            state=A2ATaskState(msg.get("state", "submitted")),
            messages=messages,
            agent_card=card,
            created_at=datetime.fromisoformat(msg["created_at"]) if "created_at" in msg else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(msg["updated_at"]) if "updated_at" in msg else datetime.now(timezone.utc),
            metadata=msg.get("metadata", {}),
        )

    def to_agent_card(self, protocol_entry: dict) -> AgentCard:
        """Convert a μACP registry entry dict to an A2A AgentCard."""
        agent_name = protocol_entry.get("agent_name") or protocol_entry.get("name", "unknown")
        capabilities = protocol_entry.get("capabilities") or protocol_entry.get("skills", [])
        return AgentCard(
            name=agent_name,
            description=protocol_entry.get("description", f"Agent: {agent_name}"),
            url=protocol_entry.get("url", self.generate_card_url(agent_name)),
            skills=capabilities if isinstance(capabilities, list) else [str(capabilities)],
            authentication=protocol_entry.get("authentication", {}),
            version=protocol_entry.get("version", "1.0"),
            metadata=protocol_entry.get("metadata", {}),
        )

    # ── A2A compatibility endpoints (FastAPI-compatible handlers) ──────────

    async def handle_agent_card_request(self, agent_name: str) -> dict:
        """Return AgentCard JSON for an agent.

        Compatible with: GET /a2a/agents/{agent_name}/card
        """
        card = await self.get_card_for_agent(agent_name)
        return {
            "jsonrpc": "2.0",
            "result": card.to_dict(),
        }

    async def handle_task_request(self, task_id: str, request_body: dict) -> dict:
        """Handle an incoming A2A task request.

        Compatible with: POST /a2a/tasks/{task_id}

        Args:
            task_id: The task identifier
            request_body: Parsed JSON body containing A2A task data
                Expected structure: {"jsonrpc": "2.0", "method": "tasks.send",
                                     "params": {"task": {...}}}

        Returns:
            A2A JSON-RPC response with the updated task
        """
        params = request_body.get("params", request_body)
        task_data = params.get("task", params) if isinstance(params, dict) else params

        if not isinstance(task_data, dict) or not task_data.get("task_id") or not task_data.get("agent_card"):
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": "Invalid task data: missing task_id or agent_card"},
            }

        task = A2ATask.from_dict(task_data)

        task.task_id = task_id
        task.state = A2ATaskState.WORKING
        task.updated_at = datetime.now(timezone.utc)
        await self._persist_task(task)

        target_agent = task.agent_card.name

        try:
            from app.agent_messaging import send_message

            msg_dict = self.to_agent_message(task)
            await send_message(
                from_agent="a2a_bridge",
                to_agent=target_agent,
                verb="ASK",
                payload=msg_dict,
                correlation_id=task.task_id,
                requires_response=True,
            )
        except Exception as e:
            logger.warning(f"[A2A] Failed to dispatch task {task_id} to {target_agent}: {e}")
            task.state = A2ATaskState.FAILED
            task.messages.append(
                A2AMessage(
                    role="agent",
                    content=[{"type": "text", "text": f"Dispatch failed: {e}"}],
                )
            )
            task.updated_at = datetime.now(timezone.utc)
            await self._persist_task(task)

        return {
            "jsonrpc": "2.0",
            "result": task.to_dict(),
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

_a2a_instance: Optional[A2AProtocolAdapter] = None


def get_a2a_protocol() -> A2AProtocolAdapter:
    """Return the singleton A2AProtocolAdapter instance."""
    global _a2a_instance
    if _a2a_instance is None:
        _a2a_instance = A2AProtocolAdapter()
        logger.info("[A2A] Singleton adapter initialised")
    return _a2a_instance


# ── Auto-registration (module load) ─────────────────────────────────────────

async def _auto_register_experts():
    """Query experts table and register A2A cards for all known agents."""
    try:
        try:
            from app.db_pool import get_pool
        except ImportError:
            from db_pool import get_pool

        pool = await get_pool()
        if not pool:
            logger.warning("[A2A] No DB pool available, skipping auto-registration")
            return

        adapter = get_a2a_protocol()

        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT name, role, department, system_prompt, metadata FROM experts ORDER BY name")
            for row in rows:
                name = row["name"]
                role = row.get("role") or ""
                department = row.get("department") or ""
                system_prompt = row.get("system_prompt") or ""
                meta = row.get("metadata") or {}

                skills = []
                if role:
                    skills.append(role)
                if department:
                    skills.append(department)
                if isinstance(meta, dict):
                    extra = meta.get("skills") or meta.get("capabilities") or []
                    if isinstance(extra, list):
                        skills.extend(extra)

                card = AgentCard(
                    name=name,
                    description=system_prompt[:200] if system_prompt else f"Expert: {name}",
                    url=adapter.generate_card_url(name),
                    skills=skills,
                    authentication={},
                    metadata={
                        "role": role,
                        "department": department,
                        "source": "experts_table",
                    },
                )
                adapter.register_agent(card)
                logger.info(f"[A2A] Auto-registered agent: {name} ({len(skills)} skills)")

        logger.info(f"[A2A] Auto-registration complete: {len(adapter._cards)} agents")
    except Exception as e:
        logger.warning(f"[A2A] Auto-registration failed (non-fatal): {e}")


def _run_auto_registration():
    """Schedule auto-registration in the running event loop, or create one."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_auto_register_experts())
    except RuntimeError:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_auto_register_experts())
        except Exception as e:
            logger.debug(f"[A2A] Cannot run auto-registration synchronously: {e}")


# Schedule auto-registration on import
try:
    _run_auto_registration()
except Exception:
    pass
