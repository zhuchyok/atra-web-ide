"""p95 KISS: category-gated enable_thinking in executor options payload."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KOS = ROOT / "knowledge_os"
EXECUTOR = ROOT / "src" / "agents" / "core" / "executor.py"


def _import_thinking_helpers():
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
    from src.agents.core.executor import build_executor_options, executor_enable_thinking

    return executor_enable_thinking, build_executor_options


def test_thinking_off_for_chat_fast_code(monkeypatch):
    enable, build = _import_thinking_helpers()
    monkeypatch.delenv("EXECUTOR_ENABLE_THINKING", raising=False)
    for cat in (None, "", "chat", "fast", "code", "coding", "general"):
        assert enable(cat) is False, cat
        opts = build(cat)
        assert opts["enable_thinking"] is False, cat
        assert opts["temperature"] == 0.1
        assert "num_predict" in opts


def test_thinking_on_for_reasoning_vip_complex(monkeypatch):
    enable, build = _import_thinking_helpers()
    monkeypatch.setenv("EXECUTOR_ENABLE_THINKING", "false")
    for cat in ("reasoning", "vip", "complex", "REASONING", "Vip"):
        assert enable(cat) is True, cat
        assert build(cat)["enable_thinking"] is True, cat


def test_env_opt_in_enables_thinking_for_chat(monkeypatch):
    enable, build = _import_thinking_helpers()
    monkeypatch.setenv("EXECUTOR_ENABLE_THINKING", "true")
    assert enable("chat") is True
    assert build("fast")["enable_thinking"] is True


def test_before_after_options_payload_contract():
    """Evidence: before was hard True; after is category-gated helper (not hard True)."""
    text = EXECUTOR.read_text(encoding="utf-8")
    assert 'os.getenv("EXECUTOR_ENABLE_THINKING", "false")' in text
    assert "_THINKING_ON_CATEGORIES" in text
    assert "def build_executor_options(" in text
    assert "def executor_enable_thinking(" in text
    assert '"enable_thinking": True' not in text
    assert "build_executor_options(category)" in text
