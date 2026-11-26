"""Tests for A2A Protocol compliance layer."""

import asyncio
import json
import uuid
from datetime import datetime, timezone

import pytest
from app.a2a_protocol import (
    A2AMessage,
    A2AProtocolAdapter,
    A2ATask,
    A2ATaskState,
    AgentCard,
    get_a2a_protocol,
)


class TestA2ADataModels:
    """Test A2A data model creation, serialization, and deserialization."""

    def test_a2a_task_state_values(self):
        assert A2ATaskState.SUBMITTED.value == "submitted"
        assert A2ATaskState.WORKING.value == "working"
        assert A2ATaskState.INPUT_REQUIRED.value == "input_required"
        assert A2ATaskState.COMPLETED.value == "completed"
        assert A2ATaskState.FAILED.value == "failed"
        assert A2ATaskState.CANCELED.value == "canceled"

    def test_agent_card_creation(self):
        card = AgentCard(
            name="Victoria",
            description="Chief Architect agent",
            url="/a2a/agents/victoria",
            skills=["planning", "coordination", "analysis"],
            authentication={"type": "none"},
        )
        assert card.name == "Victoria"
        assert len(card.skills) == 3
        assert card.version == "1.0"

    def test_agent_card_to_dict(self):
        card = AgentCard(
            name="Veronica",
            description="Executor agent",
            url="/a2a/agents/veronica",
            skills=["execution", "code"],
            authentication={"type": "api_key"},
        )
        d = card.to_dict()
        assert d["name"] == "Veronica"
        assert d["skills"] == ["execution", "code"]
        assert d["authentication"] == {"type": "api_key"}

    def test_agent_card_from_dict(self):
        data = {
            "name": "Roman",
            "description": "Heavy expert",
            "url": "/a2a/agents/roman",
            "skills": ["analysis", "review"],
            "authentication": {},
            "version": "2.0",
            "metadata": {"department": "engineering"},
        }
        card = AgentCard.from_dict(data)
        assert card.name == "Roman"
        assert card.version == "2.0"
        assert card.metadata["department"] == "engineering"

    def test_agent_card_roundtrip_json(self):
        original = AgentCard(
            name="Anna",
            description="Verification expert",
            url="/a2a/agents/anna",
            skills=["verify", "test"],
            authentication={"type": "jwt"},
            version="1.5",
            metadata={"priority": 1},
        )
        restored = AgentCard.from_dict(json.loads(json.dumps(original.to_dict())))
        assert restored.name == original.name
        assert restored.skills == original.skills
        assert restored.authentication == original.authentication

    def test_a2a_message_creation(self):
        msg = A2AMessage(
            role="user",
            content=[{"type": "text", "text": "Analyze the architecture"}],
            metadata={"session_id": "abc-123"},
        )
        assert msg.role == "user"
        assert msg.content[0]["text"] == "Analyze the architecture"

    def test_a2a_message_to_dict(self):
        msg = A2AMessage(
            role="agent",
            content=[
                {"type": "text", "text": "Analysis complete"},
                {"type": "file", "file": {"path": "/tmp/report.md"}},
            ],
        )
        d = msg.to_dict()
        assert d["role"] == "agent"
        assert len(d["content"]) == 2

    def test_a2a_message_from_dict(self):
        data = {
            "role": "user",
            "content": [{"type": "text", "text": "hello"}],
            "metadata": {"lang": "en"},
        }
        msg = A2AMessage.from_dict(data)
        assert msg.role == "user"
        assert msg.metadata["lang"] == "en"

    def test_a2a_task_creation(self):
        card = AgentCard(
            name="Victoria",
            description="Architect",
            url="/a2a/agents/victoria",
            skills=["planning"],
            authentication={},
        )
        msg = A2AMessage(role="user", content=[{"type": "text", "text": "Design the system"}])
        now = datetime.now(timezone.utc)
        task = A2ATask(
            task_id=str(uuid.uuid4()),
            state=A2ATaskState.SUBMITTED,
            messages=[msg],
            agent_card=card,
            created_at=now,
            updated_at=now,
        )
        assert task.state == A2ATaskState.SUBMITTED
        assert len(task.messages) == 1
        assert task.agent_card.name == "Victoria"

    def test_a2a_task_to_dict(self):
        card = AgentCard(
            name="Veronica",
            description="Executor",
            url="/a2a/agents/veronica",
            skills=["code"],
            authentication={},
        )
        msg = A2AMessage(role="user", content=[{"type": "text", "text": "Write code"}])
        now = datetime.now(timezone.utc)
        task = A2ATask(
            task_id="task-001",
            state=A2ATaskState.WORKING,
            messages=[msg],
            agent_card=card,
            created_at=now,
            updated_at=now,
        )
        d = task.to_dict()
        assert d["task_id"] == "task-001"
        assert d["state"] == "working"
        assert d["agent_card"]["name"] == "Veronica"

    def test_a2a_task_from_dict(self):
        data = {
            "task_id": "task-002",
            "state": "completed",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "do it"}], "metadata": {}},
                {
                    "role": "agent",
                    "content": [{"type": "text", "text": "done"}],
                    "metadata": {},
                },
            ],
            "agent_card": {
                "name": "Roman",
                "description": "Expert",
                "url": "/a2a/agents/roman",
                "skills": ["review"],
                "authentication": {},
                "version": "1.0",
                "metadata": {},
            },
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:01:00+00:00",
            "metadata": {"source": "api"},
        }
        task = A2ATask.from_dict(data)
        assert task.task_id == "task-002"
        assert task.state == A2ATaskState.COMPLETED
        assert len(task.messages) == 2
        assert task.agent_card.name == "Roman"

    def test_a2a_task_roundtrip_json(self):
        card = AgentCard(
            name="Test",
            description="Test agent",
            url="/a2a/agents/test",
            skills=["test"],
            authentication={},
        )
        msg = A2AMessage(role="user", content=[{"type": "text", "text": "run"}])
        now = datetime.now(timezone.utc)
        original = A2ATask(
            task_id="roundtrip-001",
            state=A2ATaskState.SUBMITTED,
            messages=[msg],
            agent_card=card,
            created_at=now,
            updated_at=now,
        )
        restored = A2ATask.from_dict(json.loads(json.dumps(original.to_dict())))
        assert restored.task_id == original.task_id
        assert restored.state == original.state
        assert restored.agent_card.name == original.agent_card.name


class TestA2AProtocolAdapter:
    """Test the A2AProtocolAdapter (registry and protocol mapping)."""

    def setup_method(self):
        self.adapter = A2AProtocolAdapter()

    def test_singleton(self):
        instance1 = get_a2a_protocol()
        instance2 = get_a2a_protocol()
        assert instance1 is instance2

    def test_register_and_discover_agent(self):
        card = AgentCard(
            name="TestExpert",
            description="Test expert",
            url="/a2a/agents/test-expert",
            skills=["test", "qa"],
            authentication={},
        )
        self.adapter.register_agent(card)
        discovered = self.adapter.discover_agent("TestExpert")
        assert discovered is not None
        assert discovered.name == "TestExpert"
        assert "test" in discovered.skills

    def test_discover_agents_list(self):
        self.adapter.register_agent(
            AgentCard(
                name="AgentA",
                description="A",
                url="/a2a/agents/a",
                skills=["a"],
                authentication={},
            )
        )
        self.adapter.register_agent(
            AgentCard(
                name="AgentB",
                description="B",
                url="/a2a/agents/b",
                skills=["b"],
                authentication={},
            )
        )
        agents = self.adapter.discover_agents()
        names = {a.name for a in agents}
        assert "AgentA" in names
        assert "AgentB" in names

    def test_discover_nonexistent_agent(self):
        card = self.adapter.discover_agent("NoSuchAgent")
        assert card is None

    def test_generate_card_url(self):
        url = self.adapter.generate_card_url("Виктория")
        assert "/a2a/agents/" in url
        url2 = self.adapter.generate_card_url("Veronica Agent")
        assert "veronica-agent" in url2

    async def test_get_card_for_agent_returns_generated_card_when_not_found(self):
        card = await self.adapter.get_card_for_agent("UnknownAgent")
        assert card.name == "UnknownAgent"
        assert card.url.startswith("/a2a/agents/")

    def test_to_agent_card(self):
        entry = {
            "agent_name": "Victoria",
            "capabilities": ["planning", "analysis"],
            "description": "Chief Architect",
            "url": "/custom/victoria",
            "authentication": {"type": "jwt"},
            "version": "2.0",
        }
        card = self.adapter.to_agent_card(entry)
        assert card.name == "Victoria"
        assert card.skills == ["planning", "analysis"]
        assert card.authentication["type"] == "jwt"

    def test_to_agent_card_fallback_name(self):
        entry = {"capabilities": ["x"]}
        card = self.adapter.to_agent_card(entry)
        assert card.name == "unknown"

    def test_to_agent_message(self):
        card = AgentCard(
            name="Source",
            description="Src",
            url="/a2a/agents/source",
            skills=["s"],
            authentication={},
        )
        msg = A2AMessage(role="user", content=[{"type": "text", "text": "hello"}])
        now = datetime.now(timezone.utc)
        task = A2ATask(
            task_id="msg-test",
            state=A2ATaskState.WORKING,
            messages=[msg],
            agent_card=card,
            created_at=now,
            updated_at=now,
        )
        result = self.adapter.to_agent_message(task)
        assert result["a2a_version"] == "1.0"
        assert result["task_id"] == "msg-test"
        assert result["state"] == "working"
        assert result["agent_card"]["name"] == "Source"

    def test_from_agent_message(self):
        msg_dict = {
            "a2a_version": "1.0",
            "task_id": "from-msg-001",
            "state": "completed",
            "messages": [
                {"role": "agent", "content": [{"type": "text", "text": "result"}], "metadata": {}}
            ],
            "agent_card": {
                "name": "Target",
                "description": "Tgt",
                "url": "/a2a/agents/target",
                "skills": ["t"],
                "authentication": {},
                "version": "1.0",
                "metadata": {},
            },
            "created_at": "2026-06-01T00:00:00+00:00",
            "updated_at": "2026-06-01T00:05:00+00:00",
            "metadata": {},
        }
        task = self.adapter.from_agent_message(msg_dict)
        assert task.task_id == "from-msg-001"
        assert task.state == A2ATaskState.COMPLETED
        assert task.agent_card.name == "Target"

    def test_from_agent_message_minimal(self):
        msg_dict = {"state": "submitted", "messages": []}
        task = self.adapter.from_agent_message(msg_dict)
        assert task.state == A2ATaskState.SUBMITTED
        assert task.agent_card.name == ""

    def test_task_cancel(self):
        card = AgentCard(
            name="Worker",
            description="W",
            url="/a2a/agents/worker",
            skills=["w"],
            authentication={},
        )
        msg = A2AMessage(role="user", content=[{"type": "text", "text": "do work"}])
        now = datetime.now(timezone.utc)
        task = A2ATask(
            task_id="cancel-test",
            state=A2ATaskState.WORKING,
            messages=[msg],
            agent_card=card,
            created_at=now,
            updated_at=now,
        )
        self.adapter._tasks["cancel-test"] = task

        result = asyncio.run(self.adapter.cancel_task("cancel-test"))
        assert result is True
        assert self.adapter._tasks["cancel-test"].state == A2ATaskState.CANCELED

    def test_cancel_completed_task_fails(self):
        card = AgentCard(
            name="Worker",
            description="W",
            url="/a2a/agents/worker",
            skills=["w"],
            authentication={},
        )
        msg = A2AMessage(role="user", content=[{"type": "text", "text": "done"}])
        now = datetime.now(timezone.utc)
        task = A2ATask(
            task_id="already-done",
            state=A2ATaskState.COMPLETED,
            messages=[msg],
            agent_card=card,
            created_at=now,
            updated_at=now,
        )
        self.adapter._tasks["already-done"] = task

        result = asyncio.run(self.adapter.cancel_task("already-done"))
        assert result is False

    def test_get_task_status(self):
        card = AgentCard(
            name="Worker",
            description="W",
            url="/a2a/agents/worker",
            skills=["w"],
            authentication={},
        )
        msg = A2AMessage(role="user", content=[{"type": "text", "text": "go"}])
        now = datetime.now(timezone.utc)
        task = A2ATask(
            task_id="status-test",
            state=A2ATaskState.WORKING,
            messages=[msg],
            agent_card=card,
            created_at=now,
            updated_at=now,
        )
        self.adapter._tasks["status-test"] = task

        state = asyncio.run(self.adapter.get_task_status("status-test"))
        assert state == A2ATaskState.WORKING

    def test_get_task_status_nonexistent(self):
        state = asyncio.run(self.adapter.get_task_status("no-such-task"))
        assert state is None

    async def test_handle_agent_card_request(self):
        card = AgentCard(
            name="APIExpert",
            description="API expert",
            url="/a2a/agents/api-expert",
            skills=["api"],
            authentication={},
        )
        self.adapter.register_agent(card)

        result = await self.adapter.handle_agent_card_request("APIExpert")
        assert result["jsonrpc"] == "2.0"
        assert result["result"]["name"] == "APIExpert"

    async def test_handle_task_request_invalid(self):
        result = await self.adapter.handle_task_request("bad-task", {"params": {}})
        assert "error" in result

    async def test_handle_task_request_valid(self):
        card = AgentCard(
            name="TargetAgent",
            description="Target",
            url="/a2a/agents/target",
            skills=["t"],
            authentication={},
        )
        now = datetime.now(timezone.utc)
        task = A2ATask(
            task_id="incoming-task",
            state=A2ATaskState.SUBMITTED,
            messages=[A2AMessage(role="user", content=[{"type": "text", "text": "execute"}])],
            agent_card=card,
            created_at=now,
            updated_at=now,
        )
        request_body = {
            "jsonrpc": "2.0",
            "method": "tasks.send",
            "params": {"task": task.to_dict()},
        }
        result = await self.adapter.handle_task_request("incoming-task", request_body)
        assert result["jsonrpc"] == "2.0"
        assert result["result"]["task_id"] == "incoming-task"
        assert result["result"]["state"] in ("working", "failed")


class TestA2AProtocolMapping:
    """Test bidirectional mapping between A2A and μACP."""

    def setup_method(self):
        self.adapter = A2AProtocolAdapter()

    def test_to_agent_message_contains_all_fields(self):
        card = AgentCard(
            name="Mapper",
            description="Map test",
            url="/a2a/agents/mapper",
            skills=["map"],
            authentication={"type": "bearer"},
        )
        msg = A2AMessage(role="user", content=[{"type": "text", "text": "map this"}])
        now = datetime.now(timezone.utc)
        task = A2ATask(
            task_id="map-test",
            state=A2ATaskState.SUBMITTED,
            messages=[msg],
            agent_card=card,
            created_at=now,
            updated_at=now,
            metadata={"env": "test"},
        )
        result = self.adapter.to_agent_message(task)
        assert "a2a_version" in result
        assert "task_id" in result
        assert "state" in result
        assert "messages" in result
        assert "agent_card" in result
        assert "created_at" in result
        assert "updated_at" in result
        assert result["metadata"]["env"] == "test"

    def test_roundtrip_identity(self):
        card = AgentCard(
            name="Roundtrip",
            description="Round trip test",
            url="/a2a/agents/roundtrip",
            skills=["rt"],
            authentication={},
            metadata={"key": "val"},
        )
        msg = A2AMessage(
            role="user",
            content=[{"type": "text", "text": "roundtrip"}],
            metadata={"msg_key": "msg_val"},
        )
        now = datetime.now(timezone.utc)
        original = A2ATask(
            task_id="rt-001",
            state=A2ATaskState.WORKING,
            messages=[msg],
            agent_card=card,
            created_at=now,
            updated_at=now,
        )
        agent_msg = self.adapter.to_agent_message(original)
        restored = self.adapter.from_agent_message(agent_msg)
        assert restored.task_id == original.task_id
        assert restored.state == original.state
        assert restored.agent_card.name == original.agent_card.name
        assert restored.agent_card.version == original.agent_card.version
        assert restored.messages[0].role == original.messages[0].role
        assert restored.messages[0].content == original.messages[0].content
