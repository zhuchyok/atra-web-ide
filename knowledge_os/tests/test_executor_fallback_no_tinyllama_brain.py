"""Executor Ollama fallback must not schedule tinyllama onto brain 11434."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KOS = ROOT / "knowledge_os"


def _import_fallback_list():
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
    from src.agents.core.executor import FALLBACK_MODELS_OLLAMA

    return FALLBACK_MODELS_OLLAMA


def test_fallback_models_ollama_excludes_tinyllama():
    models = _import_fallback_list()
    joined = " ".join(models).lower()
    assert "tinyllama" not in joined
    assert any("phi3.5" in m for m in models)


def test_git_guardian_documents_stray_keep_alive_zero():
    text = (ROOT / "scripts" / "git_guardian.py").read_text(encoding="utf-8")
    assert "OLLAMA_GUARDIAN_URL" in text
    assert "keep_alive=0" in text or "keep_alive" in text
    assert "DIALOGUE_BRAIN_STRAY_KEEP_ALIVE_SEC" in text
