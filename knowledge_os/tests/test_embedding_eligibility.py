"""Unit tests for RAG embedding eligibility helpers."""

from app.embedding_eligibility import content_is_rag_eligible, path_is_indexable


class TestPathIsIndexable:
    def test_rejects_venv(self):
        assert path_is_indexable("knowledge_os/venv/lib/python3.12/foo.py") is False

    def test_rejects_site_packages(self):
        assert path_is_indexable("/app/.venv/lib/python3.11/site-packages/x.py") is False

    def test_accepts_app_module(self):
        assert path_is_indexable("knowledge_os/app/ai_core.py") is True


class TestContentIsRagEligible:
    def test_rejects_short(self):
        assert content_is_rag_eligible("too short") is False

    def test_rejects_audit_type(self):
        assert (
            content_is_rag_eligible(
                "Success Retrieval Audit for: something long enough here",
                metadata_type="success_retrieval_audit",
            )
            is False
        )

    def test_rejects_venv_project_file(self):
        text = 'PROJECT_FILE: "knowledge_os/venv/lib/python3.12/site-packages/x.py"\n\n' + (
            "code " * 20
        )
        assert content_is_rag_eligible(text) is False

    def test_rejects_discovery_stub(self):
        text = "💎 ФУНДАМЕНТАЛЬНОЕ ЗНАНИЕ: 📋 Discovery фаза начата для сессии " + ("x" * 40)
        assert content_is_rag_eligible(text) is False

    def test_accepts_mentorship(self):
        text = "🎓 MENTORSHIP NOTE for Анна: always verify contracts before merge. " + (
            "detail " * 10
        )
        assert content_is_rag_eligible(text, metadata_type="mentorship_note") is True
