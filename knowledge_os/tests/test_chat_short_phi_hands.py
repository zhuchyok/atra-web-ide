"""Day-better: short chat model defaults to hands phi, not brain qwen38."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KOS = ROOT / "knowledge_os"
VS = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"
EX = ROOT / "src" / "agents" / "core" / "executor.py"


def test_select_model_short_defaults_to_phi():
    text = VS.read_text(encoding="utf-8")
    start = text.index("def _select_model_for_chat")
    end = text.index("\n# Загружаем .env при старте", start)
    block = text[start:end]
    assert 'os.getenv("VICTORIA_CHAT_SHORT_MODEL", "phi3.5:3.8b")' in block
    assert 'os.getenv("VICTORIA_MODEL", "victoria-qwen38:latest")' in block
    # Day chat must not hardcode wisdom-24k anymore.
    assert "victoria-wisdom-24k:latest" not in block


def test_fast_path_skips_enrichment_tax():
    text = VS.read_text(encoding="utf-8")
    assert "skip AI-research+DNA on simple/fast" in text
    assert "skip DNA+AB tax after generate" in text


def test_generate_skips_mlx_for_hands_phi():
    text = VS.read_text(encoding="utf-8")
    assert "VICTORIA_PHI_PREFER_HANDS" in text
    assert "prefer hands Ollama (skip MLX)" in text


def test_fast_chat_num_predict_cap(monkeypatch):
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
    from src.agents.core.executor import build_executor_options

    monkeypatch.delenv("EXECUTOR_NUM_PREDICT_FAST", raising=False)
    monkeypatch.delenv("EXECUTOR_NUM_PREDICT_CAP", raising=False)
    fast = build_executor_options("fast")
    chat = build_executor_options("chat")
    heavy = build_executor_options("reasoning")
    assert fast["num_predict"] == 256
    assert chat["num_predict"] == 256
    assert heavy["num_predict"] == 1200
    assert "EXECUTOR_NUM_PREDICT_FAST" in EX.read_text(encoding="utf-8")


def test_short_chat_skips_semantic_cache():
    text = EX.read_text(encoding="utf-8")
    assert "VICTORIA_DISABLE_SEMANTIC_CACHE_FOR_SHORT" in text
    assert "disable_short_chat_semantic_cache" in text
    assert "_skip_semantic_cache" in text
