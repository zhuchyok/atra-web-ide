"""Hands XOR: executor must normalize -stable → base before POST to 11437."""

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


def _import_executor_hands_helpers():
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
    from src.agents.core.executor import (
        _normalize_ollama_hands_model,
        _redirect_hands_model,
    )

    return _normalize_ollama_hands_model, _redirect_hands_model


def test_normalize_stable_to_base_phi():
    normalize, _ = _import_executor_hands_helpers()
    assert normalize("phi3.5:3.8b-stable") == "phi3.5:3.8b"
    assert normalize("phi3.5:3.8b") == "phi3.5:3.8b"
    assert normalize("nomic-embed-text") == "nomic-embed-text"


def test_redirect_then_normalize_before_hands_post(monkeypatch):
    """Redirect alone is not enough — stable must become base on 11437."""
    normalize, redirect = _import_executor_hands_helpers()
    monkeypatch.setenv("OLLAMA_HANDS_URL", "http://localhost:11437")
    brain = "http://localhost:11434"
    model = "phi3.5:3.8b-stable"
    hands_url = redirect(model, brain)
    assert hands_url == "http://localhost:11437"
    # Call-site contract used by Executor._ask_with_fallback
    if "11437" in (hands_url or ""):
        model = normalize(model)
    assert model == "phi3.5:3.8b"


def test_executor_source_normalizes_on_11437():
    text = (ROOT / "src" / "agents" / "core" / "executor.py").read_text(encoding="utf-8")
    assert "def _normalize_ollama_hands_model" in text
    assert 'if "11437" in (base_url or ""):' in text
    assert "model = _normalize_ollama_hands_model(model)" in text


def test_victoria_server_hands_prefs_omit_stable():
    """Live preference/maps that feed Hands must not nominate -stable."""
    text = (ROOT / "src" / "agents" / "bridge" / "victoria_server.py").read_text(
        encoding="utf-8"
    )
    # _select_model_for_task model_map + preferred_planner
    assert '"phi3.5:3.8b-stable"' not in text
    assert "phi3.5:3.8b" in text
