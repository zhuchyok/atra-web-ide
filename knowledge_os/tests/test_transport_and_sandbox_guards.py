from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_CORE = ROOT / "knowledge_os" / "app" / "ai_core.py"
SANDBOX_MANAGER = ROOT / "knowledge_os" / "app" / "sandbox_manager.py"


def test_rust_rag_defaults_to_http_and_has_tls_mismatch_retry():
    text = AI_CORE.read_text(encoding="utf-8")
    assert "http://atra-web-ide-gateway:8081/api/knowledge/search_v2" in text
    assert "WRONG_VERSION_NUMBER" in text
    assert "TLS mismatch, retrying over HTTP" in text
    assert 'fallback_url = "http://" + rust_url[len("https://") :]' in text


def test_sandbox_manager_can_infer_host_project_root_from_mounts():
    text = SANDBOX_MANAGER.read_text(encoding="utf-8")
    assert "def _infer_host_project_root_from_mounts(" in text
    assert 'destination == "/workspace/atra-web-ide"' in text
    assert 'destination == "/app/knowledge_os"' in text
    assert "self.host_shared_dir = _resolve_host_sandbox_shared_dir(self.docker_client)" in text
    assert "mount_path = self.host_shared_dir or _resolve_host_sandbox_shared_dir(self.docker_client)" in text
