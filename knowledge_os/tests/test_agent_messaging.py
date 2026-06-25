"""Tests for agent_messaging.py — Agent-to-Agent messaging layer."""

import json
import pytest
from app.agent_messaging import AgentMessage


class TestAgentMessage:
    """Test the AgentMessage dataclass and serialization."""

    def test_message_creation(self):
        msg = AgentMessage(from_agent="Victoria", to_agent="Veronica", verb="TELL", payload="hello")
        assert msg.from_agent == "Victoria"
        assert msg.to_agent == "Veronica"
        assert msg.verb == "TELL"
        assert msg.payload == "hello"
        assert msg.msg_id is not None
        assert msg.correlation_id == msg.msg_id

    def test_message_to_dict(self):
        msg = AgentMessage(from_agent="Victoria", to_agent="*", verb="ASK", payload={"q": "status?"})
        d = msg.to_dict()
        assert d["from_agent"] == "Victoria"
        assert d["to_agent"] == "*"
        assert d["verb"] == "ASK"
        assert d["payload"] == {"q": "status?"}
        assert "msg_id" in d
        assert "timestamp" in d

    def test_message_from_dict(self):
        original = AgentMessage(from_agent="Roman", to_agent="Anna", verb="TELL", payload="done")
        d = original.to_dict()
        restored = AgentMessage.from_dict(d)
        assert restored.from_agent == "Roman"
        assert restored.to_agent == "Anna"
        assert restored.verb == "TELL"
        assert restored.payload == "done"
        assert restored.msg_id == original.msg_id

    def test_message_roundtrip_json(self):
        msg = AgentMessage(from_agent="Test", to_agent="Target", verb="PING", payload={"n": 42})
        json_str = json.dumps(msg.to_dict())
        restored = AgentMessage.from_dict(json.loads(json_str))
        assert restored.from_agent == "Test"
        assert restored.verb == "PING"
        assert restored.payload == {"n": 42}

    def test_broadcast_message(self):
        msg = AgentMessage(from_agent="Victoria", to_agent="*", verb="OBSERVE", payload="status")
        assert msg.to_agent == "*"

    def test_requires_response(self):
        msg = AgentMessage(from_agent="A", to_agent="B", verb="ASK", payload="?", requires_response=True)
        assert msg.requires_response is True

    def test_custom_correlation_id(self):
        msg = AgentMessage(from_agent="A", to_agent="B", verb="TELL", payload="x", correlation_id="custom-123")
        assert msg.correlation_id == "custom-123"
