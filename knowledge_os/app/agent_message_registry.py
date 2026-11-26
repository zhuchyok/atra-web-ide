"""
Agent Message Registry — Schema registry for agent message verbs (Singularity 31.3)

Registers, validates, and maps message schemas for agent-to-agent communication.
Built-in schemas: TELL, ASK, PING, OBSERVE, HANDOFF, BROADCAST.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class MessageSchema:
    """Schema definition for one agent message verb/version pair."""

    verb: str
    version: str
    description: str
    required_fields: List[str]
    optional_fields: List[str]
    max_payload_size: int = 65536


# ── Protobuf RPC method mapping ──────────────────────────────────────────────
# Maps message verbs to .proto RPC methods from agent_protocol.proto
_PROTOBUF_RPC_MAP: Dict[str, str] = {
    "PING": "GetHealth",
    "TELL": "ProcessTask",
    "ASK": "ProcessTask",
    "OBSERVE": "GetHealth",
    "HANDOFF": "InitiateHandoff",
}


# ── Built-in schemas ─────────────────────────────────────────────────────────
_BUILTIN_SCHEMAS: List[MessageSchema] = [
    MessageSchema(
        verb="TELL",
        version="1.0",
        description="Fire-and-forget information transfer between agents",
        required_fields=["from_agent", "to_agent", "payload"],
        optional_fields=["correlation_id"],
    ),
    MessageSchema(
        verb="ASK",
        version="1.0",
        description="Request information from another agent; expects a response",
        required_fields=["from_agent", "to_agent", "payload", "correlation_id"],
        optional_fields=["requires_response", "timeout"],
    ),
    MessageSchema(
        verb="PING",
        version="1.0",
        description="Liveness check — verify an agent is reachable",
        required_fields=["from_agent", "to_agent"],
        optional_fields=[],
    ),
    MessageSchema(
        verb="OBSERVE",
        version="1.0",
        description="Observe an agent's state or capabilities",
        required_fields=["from_agent", "payload", "event_type"],
        optional_fields=["to_agent", "correlation_id"],
    ),
    MessageSchema(
        verb="HANDOFF",
        version="1.0",
        description="Explicit task handoff between agents with deadline and priority",
        required_fields=["from_agent", "to_agent", "task", "context", "deadline", "priority"],
        optional_fields=["correlation_id", "expected_output"],
    ),
    MessageSchema(
        verb="BROADCAST",
        version="1.0",
        description="Publish a message to all listening agents",
        required_fields=["from_agent", "payload", "event_type"],
        optional_fields=["correlation_id"],
    ),
    MessageSchema(
        verb="COUNTER",
        version="1.0",
        description="Decline a task with reason (overload/policy), optionally suggest alternative",
        required_fields=["from_agent", "task_id", "reason"],
        optional_fields=["to_agent", "suggestion", "load_score"],
        max_payload_size=4096,
    ),
    MessageSchema(
        verb="SUBCONTRACT",
        version="1.0",
        description="Propose decomposing a task into subtasks for different experts",
        required_fields=["from_agent", "task_id", "subtasks", "rationale"],
        optional_fields=["to_agent", "original_goal"],
        max_payload_size=16384,
    ),
    MessageSchema(
        verb="CONFLICT",
        version="1.0",
        description="Report a verification/quality conflict between experts",
        required_fields=["from_agent", "to_agent", "task_id", "issue"],
        optional_fields=["proposed_resolution", "evidence"],
        max_payload_size=32768,
    ),
]


class AgentMessageRegistry:
    """
    Central registry for agent message schemas.

    Supports registration, lookup, validation, and protobuf mapping.
    """

    def __init__(self):
        self._schemas: Dict[str, Dict[str, MessageSchema]] = {}
        self._load_builtins()

    # ── Initialisation ───────────────────────────────────────────────────

    def _load_builtins(self):
        """Register all built-in schemas at startup."""
        for schema in _BUILTIN_SCHEMAS:
            self._insert(schema)

    def _insert(self, schema: MessageSchema):
        """Insert a schema, creating the version map if needed."""
        if schema.verb not in self._schemas:
            self._schemas[schema.verb] = {}
        self._schemas[schema.verb][schema.version] = schema
        logger.debug(
            f"[MSG_REGISTRY] Registered schema {schema.verb} v{schema.version}"
        )

    # ── Schema management ─────────────────────────────────────────────────

    def register_schema(self, schema: MessageSchema):
        """Register a new message schema (overwrites existing verb+version)."""
        self._insert(schema)
        logger.info(
            f"[MSG_REGISTRY] Schema registered: {schema.verb} v{schema.version}"
        )

    def get_schema(self, verb: str, version: str = "1.0") -> Optional[MessageSchema]:
        """Look up a schema by verb and version. Returns None if not found."""
        verb_map = self._schemas.get(verb)
        if verb_map is None:
            return None
        return verb_map.get(version)

    # ── Validation ────────────────────────────────────────────────────────

    def validate_message(
        self, msg: dict, verb: str, version: str = "1.0"
    ) -> Tuple[bool, List[str]]:
        """
        Validate a message dict against the registered schema.

        Returns:
            (is_valid, errors) where errors is a list of human-readable messages.
        """
        errors: List[str] = []

        schema = self.get_schema(verb, version)
        if schema is None:
            errors.append(
                f"No schema registered for verb={verb!r} version={version!r}"
            )
            return False, errors

        # Check required fields
        for field_name in schema.required_fields:
            if field_name not in msg or msg[field_name] is None:
                errors.append(
                    f"Missing required field: {field_name!r} "
                    f"(verb={verb!r}, version={version!r})"
                )

        # Check payload size
        payload = msg.get("payload")
        if payload is not None:
            try:
                serialized = json.dumps(payload, ensure_ascii=False)
                if len(serialized) > schema.max_payload_size:
                    errors.append(
                        f"Payload exceeds max size: "
                        f"{len(serialized)} > {schema.max_payload_size} bytes"
                    )
            except (TypeError, ValueError) as exc:
                errors.append(f"Payload is not JSON-serializable: {exc}")

        # Warn on unknown fields (not an error, but logged)
        allowed = set(schema.required_fields + schema.optional_fields)
        unknown = [k for k in msg if k not in allowed and k != "payload"]
        if unknown:
            logger.debug(
                f"[MSG_REGISTRY] Unknown fields in {verb} message: {unknown}"
            )

        return len(errors) == 0, errors

    # ── Introspection ─────────────────────────────────────────────────────

    def list_verbs(self) -> List[str]:
        """Return all registered verb names, sorted."""
        return sorted(self._schemas.keys())

    def get_protobuf_mapping(self) -> Dict[str, str]:
        """Map registered verbs to their .proto RPC methods."""
        mapping: Dict[str, str] = {}
        for verb in self._schemas:
            rpc = _PROTOBUF_RPC_MAP.get(verb)
            if rpc:
                mapping[verb] = rpc
        return mapping


# ── Singleton ─────────────────────────────────────────────────────────────────

_registry_instance: Optional[AgentMessageRegistry] = None


def get_message_registry() -> AgentMessageRegistry:
    """Return the singleton registry instance, creating it if necessary."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = AgentMessageRegistry()
        logger.info("[MSG_REGISTRY] Singleton registry initialised")
    return _registry_instance
