"""Tests for Veronica bridge /metrics (src/agents/bridge/server.py)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
KOS = ROOT / "knowledge_os"


def _import_veronica_app():
    """Import Veronica FastAPI app with repo root first (avoid knowledge_os shadowing src)."""
    root_s = str(ROOT)
    kos_s = str(KOS)
    cleaned = []
    for p in sys.path:
        try:
            rp = str(Path(p).resolve())
        except Exception:
            rp = p
        if rp == kos_s or rp.endswith("/knowledge_os"):
            continue
        cleaned.append(p)
    sys.path[:] = [root_s] + [p for p in cleaned if p != root_s]
    for key in list(sys.modules):
        if key == "src" or key.startswith("src.") or key in ("app",):
            del sys.modules[key]
    os.environ.setdefault("USE_KNOWLEDGE_OS", "false")
    os.environ.setdefault("USE_ELK", "false")
    from src.agents.bridge.server import agent, app

    return app, agent


@pytest.fixture(scope="module")
def veronica_client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    app, agent = _import_veronica_app()
    with TestClient(app) as client:
        yield client, agent


class TestVeronicaMetrics:
    """Hit the real Veronica /metrics endpoint (no hardcoded exposition strings)."""

    def test_metrics_http_ok_and_prometheus_shape(self, veronica_client):
        client, agent = veronica_client
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers.get("content-type", "")
        text = resp.text
        assert "# HELP" in text
        assert "# TYPE" in text
        assert "veronica_info" in text
        assert "veronica_up" in text
        assert "veronica_tasks_total" in text
        assert text.count("# HELP") == 3
        assert text.count("# TYPE") == 3
        assert f'veronica_info{{agent="{agent.name}"}}' in text
        assert "veronica_up 1" in text

    def test_metrics_parseable_lines(self, veronica_client):
        client, _agent = veronica_client
        text = client.get("/metrics").text
        lines = [ln for ln in text.strip().split("\n") if ln]
        help_lines = [ln for ln in lines if ln.startswith("# HELP")]
        type_lines = [ln for ln in lines if ln.startswith("# TYPE")]
        sample_lines = [ln for ln in lines if not ln.startswith("#")]
        assert len(help_lines) == 3
        assert len(type_lines) == 3
        assert any(ln.startswith("veronica_up") for ln in sample_lines)
        assert any(ln.startswith("veronica_info{") for ln in sample_lines)
        assert any(ln.startswith("veronica_tasks_total{") for ln in sample_lines)

    def test_agent_name_in_metrics_labels(self, veronica_client):
        client, agent = veronica_client
        text = client.get("/metrics").text
        assert agent.name
        assert f'agent="{agent.name}"' in text

    def test_metrics_no_prometheus_client_dep(self, veronica_client):
        """Endpoint returns plaintext without importing prometheus_client."""
        client, _agent = veronica_client
        resp = client.get("/metrics")
        assert resp.status_code == 200
        body = resp.content
        assert isinstance(body, (bytes, bytearray))
        assert b"veronica_up" in body
        # Design: hand-rolled exposition, not generate_latest()
        server_src = (ROOT / "src" / "agents" / "bridge" / "server.py").read_text(encoding="utf-8")
        metrics_block = server_src.split('@app.get("/metrics")', 1)[1].split("if __name__", 1)[0]
        assert "generate_latest" not in metrics_block
        assert "import prometheus_client" not in metrics_block
        assert "from prometheus_client" not in metrics_block
