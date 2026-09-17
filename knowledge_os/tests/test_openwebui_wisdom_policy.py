"""Open WebUI must not ping Ollama wisdom (that loads 11434)."""

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "ensure_openwebui_victoria_policy.py"


def _load():
    spec = importlib.util.spec_from_file_location("ensure_openwebui_victoria_policy", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_disable_ollama_wisdom_when_mlx_healthy():
    mod = _load()
    assert mod.should_disable_ollama_wisdom(True) is True
    assert mod.should_disable_ollama_wisdom(False) is False


def test_policy_script_never_posts_generate():
    text = _SCRIPT.read_text(encoding="utf-8")
    assert "/api/generate" not in text
    assert '"ping"' not in text
