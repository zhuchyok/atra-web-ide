import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
APP_ROOT = os.path.join(ROOT, "knowledge_os", "app")
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)


class _FakeConn:
    async def fetchrow(self, query, *args):
        # domain_cache.get_domain_id() asks for id by name
        if "FROM domains WHERE name" in query:
            return {"id": "domain-1"}
        return None

    async def fetch(self, query, *args):
        if "SELECT content, metadata, domain_id" in query:
            # All candidates are intentionally below strict cutoff.
            return [
                {
                    "content": "low-sim chunk A",
                    "metadata": {"source": "indexing_daemon", "file_path": "a.md"},
                    "domain_id": "domain-1",
                    "similarity": 0.20,
                },
                {
                    "content": "low-sim chunk B",
                    "metadata": {"source": "indexing_daemon", "file_path": "b.md"},
                    "domain_id": "domain-1",
                    "similarity": 0.18,
                },
            ]
        return []


class _AcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self):
        self._conn = _FakeConn()

    def acquire(self):
        return _AcquireCtx(self._conn)


class _FakeGraphRag:
    async def retrieve_graph_context(self, query):
        return "", []


@pytest.mark.asyncio
async def test_similarity_cutoff_falls_back_to_topk(monkeypatch):
    from app import ai_core
    from app.graphrag import graphrag_service

    monkeypatch.setenv("RAG_MIN_SIMILARITY", "0.95")
    monkeypatch.setenv("RAG_MIN_SIMILARITY_FALLBACK_TOPK", "1")
    monkeypatch.setenv("RAG_RERANKER_ENABLED", "false")
    monkeypatch.setenv("KNOWLEDGE_RAG_TIMEOUT_SEC", "5")
    monkeypatch.setenv("RUST_GATEWAY_URL", "http://127.0.0.1:9")

    async def _fake_get_db_pool():
        return _FakePool()

    async def _fake_get_embedding(_query):
        return [0.1, 0.2, 0.3]

    async def _fake_deep_memory(_rows, _pool):
        return ""

    monkeypatch.setattr(ai_core, "_get_db_pool", _fake_get_db_pool)
    monkeypatch.setattr(ai_core, "get_embedding", _fake_get_embedding)
    monkeypatch.setattr(ai_core, "_enrich_with_deep_memory", _fake_deep_memory)
    monkeypatch.setattr(graphrag_service, "get_graphrag_service", lambda: _FakeGraphRag())

    context = await ai_core._get_knowledge_context_impl("short query")

    # Before fallback fix this could become an empty context ("").
    assert context
    assert "[KNOWLEDGE CONTEXT" in context


class _NamespaceConn(_FakeConn):
    async def fetch(self, query, *args):
        if "SELECT content, metadata, domain_id" in query:
            return [
                {
                    "content": "KSENIA_SECRET_MARKER own domain note",
                    "metadata": {
                        "source": "indexing_daemon",
                        "file_path": "ksenia.md",
                        "expert_name": "Ксения",
                    },
                    "domain_id": "domain-1",
                    "similarity": 0.91,
                },
                {
                    "content": "project README generic doc",
                    "metadata": {"source": "indexing_daemon", "file_path": "README.md"},
                    "domain_id": "domain-1",
                    "similarity": 0.88,
                },
                {
                    "content": "YULIA_SECRET_MARKER attack_report ИНН",
                    "metadata": {
                        "source": "indexing_daemon",
                        "file_path": "yulia.md",
                        "expert_name": "Юлия",
                    },
                    "domain_id": "domain-1",
                    "similarity": 0.96,
                },
            ]
        return []


class _NamespacePool(_FakePool):
    def __init__(self):
        self._conn = _NamespaceConn()


@pytest.mark.asyncio
async def test_namespace_drops_foreign_expert_chunks(monkeypatch):
    from app import ai_core
    from app.graphrag import graphrag_service
    from task_isolation import bind_task_context

    monkeypatch.setenv("RAG_MIN_SIMILARITY", "0.45")
    monkeypatch.setenv("RAG_RERANKER_ENABLED", "false")
    monkeypatch.setenv("RAG_NAMESPACE_FILTER", "true")
    monkeypatch.setenv("KNOWLEDGE_RAG_TIMEOUT_SEC", "5")
    monkeypatch.setenv("RUST_GATEWAY_URL", "http://127.0.0.1:9")

    async def _fake_get_db_pool():
        return _NamespacePool()

    async def _fake_get_embedding(_query):
        return [0.1, 0.2, 0.3]

    async def _fake_deep_memory(_rows, _pool):
        return ""

    monkeypatch.setattr(ai_core, "_get_db_pool", _fake_get_db_pool)
    monkeypatch.setattr(ai_core, "get_embedding", _fake_get_embedding)
    monkeypatch.setattr(ai_core, "_enrich_with_deep_memory", _fake_deep_memory)
    monkeypatch.setattr(graphrag_service, "get_graphrag_service", lambda: _FakeGraphRag())

    async with bind_task_context("task-b", "Ксения"):
        context = await ai_core._get_knowledge_context_impl("short query")

    assert context
    assert "YULIA_SECRET_MARKER" not in context
    assert "KSENIA_SECRET_MARKER" in context
    assert "project README" in context
    assert "СПРАВОЧНЫЙ КОНТЕКСТ (не задание)" in context
