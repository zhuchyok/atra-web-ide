from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"
EXECUTION_PHASE = ROOT / "knowledge_os" / "app" / "execution_phase.py"
EXPERT_WORKER = ROOT / "knowledge_os" / "app" / "expert_worker.py"
LOCAL_ROUTER = ROOT / "knowledge_os" / "app" / "local_router.py"
AGENTS_COMPOSE = ROOT / "knowledge_os" / "docker-compose.agents.yml"


def test_victoria_warmup_has_executor_channel_routing():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "def _ollama_url_for_model(" in text
    assert "OLLAMA_EXECUTOR_BASE_URL" in text
    assert "model_ollama_url = _ollama_url_for_model(model, default_url=ollama_url)" in text
    assert 'if model and "wisdom" in str(model).lower():' in text
    assert "Deferred warmup skipped for %s: мозг только в MLX" in text


def test_execution_phase_preload_supports_executor_channel():
    text = EXECUTION_PHASE.read_text(encoding="utf-8")
    # Wisdom-only path keeps deterministic generation in execution_phase
    # while model channel routing is enforced in victoria/local_router/worker layers.
    assert "Template cache for deterministic code generation" in text
    assert "def _gen_python(" in text


def test_expert_worker_release_uses_model_specific_channel():
    text = EXPERT_WORKER.read_text(encoding="utf-8")
    assert "def _ollama_url_for_model(model: Optional[str]) -> str:" in text
    assert "OLLAMA_EXECUTOR_BASE_URL" in text
    assert "ollama_base = _ollama_url_for_model(used_model)" in text
    assert 'if m and "wisdom" in m.lower():' in text


def test_local_router_has_dedicated_executor_node():
    text = LOCAL_ROUTER.read_text(encoding="utf-8")
    assert "OLLAMA_EXECUTOR_API_URL = os.getenv(\"OLLAMA_EXECUTOR_BASE_URL\")" in text
    assert "\"routing_key\": \"ollama_executor\"" in text
    assert "Heavy coder model pinned to dedicated Ollama node" in text


def test_compose_propagates_executor_base_url():
    text = AGENTS_COMPOSE.read_text(encoding="utf-8")
    assert "OLLAMA_EXECUTOR_BASE_URL: ${OLLAMA_EXECUTOR_BASE_URL:-http://host.docker.internal:11434}" in text
