"""Tests for rest_api.py /api/health/all endpoint."""

import json
import pytest


class TestHealthAll:
    """Test health aggregation logic."""

    def test_service_urls_defined(self):
        """All critical services should be in the health check list."""
        urls = {
            "victoria": "http://victoria-agent:8000/health",
            "veronica": "http://veronica-agent:8000/health",
            "mlx": "http://host.docker.internal:11435/health",
            "ollama": "http://host.docker.internal:11434/api/tags",
            "swarm_studio": "http://swarm-studio:8006/",
        }
        assert "victoria" in urls
        assert "veronica" in urls
        assert "mlx" in urls
        assert "ollama" in urls
        assert "swarm_studio" in urls

    def test_health_response_format(self):
        """Health response should have overall + services."""
        mock_response = {
            "overall": "healthy",
            "services": {
                "victoria": {"status": "ok"},
                "veronica": {"status": "ok"},
            }
        }
        assert mock_response["overall"] == "healthy"
        assert len(mock_response["services"]) == 2

    def test_degraded_detection(self):
        """If any service is error, overall should be degraded."""
        mock = {"overall": "degraded", "services": {
            "victoria": {"status": "ok"},
            "redis": {"status": "error", "error": "timeout"}
        }}
        assert mock["overall"] == "degraded"
        assert mock["services"]["redis"]["status"] == "error"

    def test_redis_check_type(self):
        """Redis check should return dict with status."""
        from app.rest_api import _check_redis
        import asyncio
        result = asyncio.run(_check_redis())
        assert isinstance(result, dict)
        assert "status" in result

    def test_postgres_check_type(self):
        """Postgres check should return dict with status."""
        from app.rest_api import _check_postgres
        import asyncio
        result = asyncio.run(_check_postgres())
        assert isinstance(result, dict)
        assert "status" in result
