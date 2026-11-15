"""Hands XOR: smollm/tinyllama/moondream must NOT be forced onto 11437."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KOS = ROOT / "knowledge_os"
APP = KOS / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _import_redirect_hands_model():
    """Prefer repo-root src/ over knowledge_os/src stub package."""
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
        if key == "src" or key.startswith("src."):
            del sys.modules[key]
    from src.agents.core.executor import _redirect_hands_model

    return _redirect_hands_model


def test_hands_markers_xor_only_phi_and_nomic():
    from local_router import _HANDS_MODEL_MARKERS, is_hands_model

    assert _HANDS_MODEL_MARKERS == ("phi3.5", "nomic")
    assert is_hands_model("phi3.5:3.8b") is True
    assert is_hands_model("nomic-embed-text:latest") is True
    for name in ("smollm2:360m", "tinyllama:1.1b-chat", "moondream:latest"):
        assert is_hands_model(name) is False, name


def test_coder_solo_gate_does_not_treat_light_non_hands_as_hands():
    from local_router import skip_hands_on_coder_slot

    assert skip_hands_on_coder_slot("http://localhost:11436", "tinyllama:1.1b-chat") is False
    assert skip_hands_on_coder_slot("http://localhost:11436", "smollm2:360m") is False
    assert skip_hands_on_coder_slot("http://localhost:11436", "moondream:latest") is False
    assert skip_hands_on_coder_slot("http://localhost:11436", "phi3.5:3.8b") is True


def test_executor_redirect_leaves_non_resident_on_11434(monkeypatch):
    redirect = _import_redirect_hands_model()
    monkeypatch.setenv("OLLAMA_HANDS_URL", "http://localhost:11437")
    brain = "http://localhost:11434"
    assert redirect("phi3.5:3.8b", brain) == "http://localhost:11437"
    assert redirect("nomic-embed-text", brain) == "http://localhost:11437"
    for name in ("smollm2:360m", "tinyllama:1.1b-chat", "moondream:latest"):
        assert redirect(name, brain) == brain, name


def test_ollama_light_hands_excludes_tinyllama():
    from available_models_scanner import _OLLAMA_LIGHT_HANDS

    joined = " ".join(_OLLAMA_LIGHT_HANDS).lower()
    assert "phi3.5" in joined
    assert "tinyllama" not in joined
    assert "smollm" not in joined
    assert "moondream" not in joined


def test_dialogue_llm_still_defaults_to_11434_vision_does_not():
    """Guardian/dialogue may stay on 11434; vision must not invent brain URL."""
    dialogue = (APP / "dialogue_llm.py").read_text(encoding="utf-8")
    vision = (APP / "vision_processor.py").read_text(encoding="utf-8")
    assert "11434" in dialogue
    assert "smollm2:360m" in dialogue
    # Hands phi must be routed to 11437 (not posted to brain).
    assert "OLLAMA_HANDS_URL" in dialogue
    assert "11437" in dialogue
    assert 'VISION_MODEL = os.getenv("VISION_MODEL", "moondream")' in vision
    assert "OLLAMA_VISION_URL" in vision
    assert "host.docker.internal:11434" not in vision
    assert 'os.getenv("MAC_LLM_URL", "http://localhost:11434")' not in vision


def test_extended_thinking_source_does_not_redirect_non_resident_to_hands():
    text = (APP / "extended_thinking.py").read_text(encoding="utf-8")
    # XOR redirect tuple must not include the unload-churn models.
    assert 'for t in ("phi3.5", "nomic")):' in text
    assert 'for t in ("phi3.5", "nomic", "smollm", "tinyllama", "moondream")' not in text


def test_hands_gate_source_blocks_non_xor_on_11437():
    """Priority-0 hands node must not accept tinyllama/smollm/moondream."""
    text = (APP / "local_router.py").read_text(encoding="utf-8")
    assert 'if "11437" in node_url_base and model and not is_hands_model(model):' in text
    assert "HANDS-GATE] %s не на руках (11437 XOR)" in text
    # Old brain-only hands gate must be gone (too narrow for XOR).
    assert 'or "qwen3.8" in (model or "").lower()\n            ):' not in text
