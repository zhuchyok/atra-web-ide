"""Day latency: chat fast-path gates on user text, not LTM-inflated goal."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"


def _chat_completions_region() -> str:
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    start = text.index('@app.post("/v1/chat/completions")')
    rest = text[start + 1 :]
    nxt = rest.find("\n@app.")
    return text[start : start + 1 + nxt] if nxt != -1 else text[start:]


def test_fastpath_gates_on_user_msg_len_not_inflated_goal():
    region = _chat_completions_region()
    assert 'len(_user_msg_text or "") < 2000' in region
    # Must not gate conversational fast-path on inflated task_req.goal.
    assert "len(task_req.goal) < 2000" not in region


def test_prefork_fastpath_exists_for_stream():
    region = _chat_completions_region()
    assert "pre-fork knowledge fast-path" in region or "pre-fork fast-path" in region
    assert "_pre_fast_content" in region


def test_omni_rag_gated_to_knowledge_markers():
    region = _chat_completions_region()
    assert "skip Omni-RAG (chat/LTM, not knowledge/fact)" in region
    assert "_want_omni_rag" in region


def test_ltm_skips_busy_stubs():
    region = _chat_completions_region()
    assert "skip LTM save for busy/handoff stub" in region
    assert "Задача ещё выполняется" in region


def test_chat_use_enhanced_not_always_true_for_conversational():
    region = _chat_completions_region()
    # Initial True is ok; must be overwritten from exec/docs/fact flags.
    assert "task_req.use_enhanced = bool(" in region
    assert "_is_execution_task_early" in region
