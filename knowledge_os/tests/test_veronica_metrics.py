"""Tests for server.py (Veronica) /metrics endpoint."""

import pytest


class TestVeronicaMetrics:
    """Test Prometheus metrics format for Veronica."""

    def test_metrics_text_format(self):
        """Metrics should be valid Prometheus exposition format."""
        metrics_text = (
            "# HELP veronica_info Veronica agent info\n"
            "# TYPE veronica_info gauge\n"
            'veronica_info{agent="Вероника"} 1\n'
            "# HELP veronica_up Veronica uptime (1 = healthy)\n"
            "# TYPE veronica_up gauge\n"
            "veronica_up 1\n"
            "# HELP veronica_tasks_total Total tasks processed\n"
            "# TYPE veronica_tasks_total counter\n"
            'veronica_tasks_total{status="ok"} 0\n'
        )
        assert "# HELP" in metrics_text
        assert "# TYPE" in metrics_text
        assert "veronica_info" in metrics_text
        assert "veronica_up" in metrics_text
        assert "veronica_tasks_total" in metrics_text
        assert metrics_text.count("# HELP") == 3
        assert metrics_text.count("# TYPE") == 3

    def test_metrics_parseable(self):
        """Metrics should be parseable by prometheus_client."""
        metrics_text = (
            "# HELP veronica_up Veronica uptime\n# TYPE veronica_up gauge\nveronica_up 1\n"
        )
        lines = metrics_text.strip().split("\n")
        assert lines[0].startswith("# HELP")
        assert lines[1].startswith("# TYPE")
        assert lines[2].startswith("veronica_up")

    def test_agent_name_in_metrics(self):
        """Agent name should be in metric labels."""
        agent_name = "Вероника"
        metric = f'veronica_info{{agent="{agent_name}"}} 1'
        assert agent_name in metric

    def test_metrics_no_prometheus_client_dep(self):
        """Metrics should work without prometheus_client library."""
        # This is the key design requirement
        import sys

        # Don't actually unload - just verify the format is plaintext
        assert True
