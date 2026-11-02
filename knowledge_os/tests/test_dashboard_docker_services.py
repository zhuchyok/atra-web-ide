import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DASH = os.path.join(ROOT, "knowledge_os", "dashboard")
if DASH not in sys.path:
    sys.path.insert(0, DASH)

from docker_services import is_autonomous_service, summarize_container


def test_filters_workers_and_agents():
    assert is_autonomous_service("knowledge_os-expert-worker-dynamic-1-1", "expert-worker-dynamic-1")
    assert is_autonomous_service("victoria-agent", "victoria-agent")
    assert is_autonomous_service("knowledge_os_orchestrator", "")
    assert not is_autonomous_service("knowledge_postgres", "knowledge_postgres")
    assert not is_autonomous_service("corporation-dashboard", "corporation-dashboard")


def test_summarize_proxy_payload():
    raw = {
        "Id": "9a0f7f4f2dedabcdef",
        "Names": ["/knowledge_os-expert-worker-dynamic-1-1"],
        "State": "running",
        "Status": "Up 19 minutes (healthy)",
        "Image": "knowledge_os-expert-worker-dynamic-1",
        "Labels": {"com.docker.compose.service": "expert-worker-dynamic-1"},
    }
    out = summarize_container(raw)
    assert out["name"] == "knowledge_os-expert-worker-dynamic-1-1"
    assert out["id"] == "9a0f7f4f2ded"
    assert "healthy" in out["status"]
    assert out["compose_service"] == "expert-worker-dynamic-1"
