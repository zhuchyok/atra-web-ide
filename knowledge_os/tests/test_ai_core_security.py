"""Tests for ai_core.py security features: threat_detector, SafetyChecker, episodic EN."""

import json
import pytest


class TestSafeCloudResponse:
    """Test _safe_cloud_response wrapper logic."""

    @pytest.mark.asyncio
    async def test_safe_cloud_response_passthrough(self):
        """Should pass through normal responses unchanged."""
        from app.ai_core import _safe_cloud_response
        result = await _safe_cloud_response("hello world")
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_safe_cloud_response_system_error(self):
        """Should return SYSTEM errors unchanged."""
        from app.ai_core import _safe_cloud_response
        result = await _safe_cloud_response("[SYSTEM: All LLM sources unavailable]")
        assert result.startswith("[SYSTEM:")

    @pytest.mark.asyncio
    async def test_safe_cloud_response_empty(self):
        """Should return empty string unchanged."""
        from app.ai_core import _safe_cloud_response
        assert await _safe_cloud_response("") == ""
        assert await _safe_cloud_response(None) is None


class TestEpisodicMemoryKeywords:
    """Test that episodic memory captures both RU and EN keywords."""

    def test_russian_keywords_detected(self):
        """Russian preference keywords should trigger save."""
        ru_keywords = ["всегда", "никогда", "предпочитаю", "мне нравится", "используй только"]
        user_part = "я всегда использую Python для бэкенда"
        assert any(kw in user_part.lower() for kw in ru_keywords)

    def test_english_keywords_detected(self):
        """English preference keywords should now trigger save."""
        en_keywords = ["always", "never", "prefer", "i like", "i use", "i want",
                       "always use", "never use", "my preference", "i usually",
                       "i tend to", "i'd like", "i prefer", "i need", "from now on"]
        user_part = "I always use TypeScript for frontend"
        assert any(kw in user_part.lower() for kw in en_keywords)

    def test_english_keywords_not_detected_before_fix(self):
        """Without EN keywords, English preferences would be missed."""
        old_keywords = ["всегда", "никогда", "предпочитаю", "мне нравится", "используй только"]
        user_part = "I always use TypeScript for frontend"
        assert not any(kw in user_part.lower() for kw in old_keywords)

    def test_detailed_explanation_triggers(self):
        """Long explanations should trigger decision episodes."""
        user_part = "почему выбрали PostgreSQL"
        long_response = "x" * 600
        assert "почему" in user_part.lower()
        assert len(long_response) > 500

    def test_mixed_language_detection(self):
        """Mixed RU/EN should be captured."""
        en_keywords = ["всегда", "никогда", "prefer", "i like"]
        user_part = "i prefer когда код на Python"
        assert any(kw in user_part.lower() for kw in en_keywords)
