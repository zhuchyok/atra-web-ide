import pytest
from app.ingestion.quality_gate import GateDecision
from app.long_term_memory import LongTermMemory
from app.services.knowledge_service import KnowledgeService


class _FakeConn:
    async def execute(self, *args, **kwargs):
        return None


class _FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


class _FakePool:
    def __init__(self):
        self.conn = _FakeConn()

    def acquire(self):
        return _FakeAcquire(self.conn)


@pytest.mark.asyncio
async def test_ltm_hard_rejects_parse_error_dumps(monkeypatch):
    async def _fake_get_pool():
        return _FakePool()

    async def _fake_embedding(_):
        raise AssertionError("Embedding must not run for hard-rejected dumps")

    async def _log_reject(*args, **kwargs):
        return True

    monkeypatch.setattr("app.long_term_memory.get_pool", _fake_get_pool)
    monkeypatch.setattr("app.long_term_memory.get_embedding", _fake_embedding)

    ltm = LongTermMemory()
    monkeypatch.setattr(ltm.quality_gate, "log_reject", _log_reject)

    dump = 'Ошибка парсинга ответа модели. Ответ: {"action": "create_file", "path": "x.md"}'
    assert await ltm.store_memory(dump, "react_agent") is None


@pytest.mark.asyncio
async def test_ltm_rejects_before_embedding(monkeypatch):
    async def _fake_get_pool():
        return _FakePool()

    async def _fake_embedding(_):
        raise AssertionError("Embedding should not be called for rejected candidate")

    async def _eval_async(*args, **kwargs):
        return GateDecision("reject", "prompt_artifact", 0.0)

    async def _log_reject(*args, **kwargs):
        return True

    monkeypatch.setattr("app.long_term_memory.get_pool", _fake_get_pool)
    monkeypatch.setattr("app.long_term_memory.get_embedding", _fake_embedding)

    ltm = LongTermMemory()
    monkeypatch.setattr(ltm.quality_gate, "evaluate_async", _eval_async)
    monkeypatch.setattr(ltm.quality_gate, "should_block", lambda decision: True)
    monkeypatch.setattr(ltm.quality_gate, "log_reject", _log_reject)

    result = await ltm.store_memory("Role: Victoria\nTone: Professional", "agent")
    assert result is None


@pytest.mark.asyncio
async def test_knowledge_service_rejects_before_embedding(monkeypatch):
    async def _fake_get_pool():
        return _FakePool()

    async def _fake_embedding(_):
        raise AssertionError("Embedding should not be called for rejected insight")

    async def _eval_async(*args, **kwargs):
        return GateDecision("reject", "prompt_artifact", 0.0)

    async def _log_reject(*args, **kwargs):
        return True

    monkeypatch.setattr("app.services.knowledge_service.get_pool", _fake_get_pool)
    monkeypatch.setattr("app.services.knowledge_service.get_embedding", _fake_embedding)

    service = KnowledgeService()
    monkeypatch.setattr(service.quality_gate, "evaluate_async", _eval_async)
    monkeypatch.setattr(service.quality_gate, "should_block", lambda decision: True)
    monkeypatch.setattr(service.quality_gate, "log_reject", _log_reject)

    result = await service.save_insight("Role: Victoria\nTone: Professional", "Victoria", {})
    assert result is None
