"""Regression: /run and chat must use deterministic fact mode for live metrics."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"


def test_run_has_deterministic_fact_mode_probe():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "async def _build_live_fact_answer_for_run(goal: str) -> Optional[str]:" in text
    assert 'if not is_fact_seeking_question(goal or ""):' in text
    assert 'strategy": "fact_live_probe"' in text
    assert 'source": "postgres_live"' in text
    assert 'fact_mode": True' in text
    assert "_live_ollama_slots_line" in text
    assert "/api/ps" in text
    assert "goal_wants_ollama_slots" in text
    assert "_live_scanner_line" in text
    assert "goal_wants_scanner" in text
    assert "unrecognized stream" in text
    assert "сканер не сняла" in text


def test_chat_fast_path_excludes_fact_questions():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "_is_fact_q = is_fact_seeking_question(_user_msg_text)" in text
    # ruff format рвёт условие на строки — сверяем по нормализованному тексту
    flat = " ".join(text.split())
    assert "and not _is_fact_q" in flat
