import os
import sys
from unittest.mock import AsyncMock

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
APP_ROOT = os.path.join(ROOT, "knowledge_os", "app")
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from app import nightly_learner


class _FakeConn:
    def __init__(self):
        self.insert_payloads = []

    async def fetchrow(self, query, *args):
        if "SELECT id FROM experts" in query:
            return {"id": "expert-1"}
        return None

    async def fetchval(self, query, *args):
        if "SELECT count(*) FROM tasks" in query:
            # No active debates in queue.
            return 0
        if "INSERT INTO tasks" in query:
            self.insert_payloads.append((query, args))
            return "task-1"
        return None


@pytest.mark.asyncio
async def test_create_debate_skipped_when_flag_disabled(monkeypatch):
    conn = _FakeConn()
    monkeypatch.setenv("HYPOTHESIS_DEBATES_ENABLED", "false")
    monkeypatch.setattr(nightly_learner, "run_expert_council", AsyncMock(return_value="council-x"))
    task_id = await nightly_learner.create_debate_for_hypothesis(
        conn=conn,
        knowledge_node_id="kn-off",
        hypothesis_text="гипотеза не должна стать pending",
        complexity="simple",
    )
    assert task_id is None
    assert conn.insert_payloads == []


@pytest.mark.asyncio
async def test_simple_debate_forces_hands_routing(monkeypatch):
    conn = _FakeConn()
    monkeypatch.setenv("HYPOTHESIS_DEBATES_ENABLED", "true")
    monkeypatch.setenv("NIGHTLY_DEBATE_SIMPLE_MODEL", "phi3.5:3.8b-stable")
    monkeypatch.setattr(nightly_learner, "run_expert_council", AsyncMock(return_value="council-1"))

    task_id = await nightly_learner.create_debate_for_hypothesis(
        conn=conn,
        knowledge_node_id="kn-1",
        hypothesis_text="Короткая гипотеза без SQL про улучшение качества ответа.",
        complexity="simple",
    )

    assert task_id == "task-1"
    assert conn.insert_payloads, "INSERT должен быть вызван"
    _, args = conn.insert_payloads[0]
    metadata_json = args[-1]
    # [v150.68] simple default source=mlx (quality-first), model from env.
    assert '"preferred_source": "mlx"' in metadata_json
    assert '"preferred_model": "phi3.5:3.8b-stable"' in metadata_json


@pytest.mark.asyncio
async def test_complex_debate_forces_brain_routing(monkeypatch):
    conn = _FakeConn()
    monkeypatch.setenv("HYPOTHESIS_DEBATES_ENABLED", "true")
    monkeypatch.setattr(nightly_learner, "run_expert_council", AsyncMock(return_value="council-2"))

    task_id = await nightly_learner.create_debate_for_hypothesis(
        conn=conn,
        knowledge_node_id="kn-2",
        hypothesis_text="Сложная SQL-гипотеза: SELECT ... про архитектурные компромиссы.",
        complexity="complex",
    )

    assert task_id == "task-1"
    assert conn.insert_payloads, "INSERT должен быть вызван"
    _, args = conn.insert_payloads[0]
    metadata_json = args[-1]
    assert '"preferred_source": "mlx"' in metadata_json
    assert '"preferred_model"' not in metadata_json
