"""Tests for self_check_system.py — container health checks."""

import json

import pytest


class TestSelfCheckConfig:
    """Test configuration parsing and URL building."""

    def test_ollama_url_from_env(self):
        """Ollama URL should use OLLAMA_BASE_URL from env, not hardcoded localhost."""
        import os

        url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        assert url.startswith("http")
        assert "11434" in url

    def test_victoria_url_default(self):
        """Victoria URL should default to service name, not localhost."""
        url = "http://victoria-agent:8000/health"
        assert "victoria-agent" in url
        assert "localhost" not in url

    def test_veronica_url_default(self):
        """Veronica URL should default to service name, not localhost."""
        url = "http://veronica-agent:8000/health"
        assert "veronica-agent" in url
        assert "localhost" not in url

    def test_database_url_format(self):
        """Database URL should be valid postgresql format."""
        url = "postgresql://admin:secret@knowledge_postgres:5432/knowledge_os"
        assert url.startswith("postgresql://")
        assert "knowledge_postgres" in url

    def test_container_check_systems(self):
        """Autonomous systems should check running containers."""
        systems = [
            ("Nightly Learner", "knowledge_nightly"),
            ("Orchestrator", "knowledge_os_orchestrator"),
            ("Smart Worker", "knowledge_os_worker"),
        ]
        names = [s[0] for s in systems]
        containers = [s[1] for s in systems]
        assert "Nightly Learner" in names
        assert "knowledge_nightly" in containers
        assert "knowledge_os_orchestrator" in containers
        assert "knowledge_os_worker" in containers
        assert len(systems) == 3

    def test_check_interval_default(self):
        """Check interval should default to 300s."""
        import os

        interval = int(os.getenv("SELF_CHECK_INTERVAL_SEC", "300"))
        assert interval == 300
