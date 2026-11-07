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
    assert "log_scanner_last.json" in text
    assert "сканер не сняла" in text
    fn = text.split("async def _fail_orphaned_inflight_on_startup", 1)[1].split(
        "def _percentile", 1
    )[0]
    assert '_sc in ("human", "runbook")' in fn
    assert '"class=human" in _goal_l' in fn
    assert "это шаблон" in fn
    assert "orphan inflight scan n=" in fn
    assert "wait_for(client.hgetall" in fn
    assert "victoria:orphan-pass" in fn
    assert "victoria:orphan-claim:" not in fn
    assert "→ resumed" in fn
    resume_fn = fn.split("→ resumed", 1)[1].split("continue", 1)[0]
    assert "_create_tracked_task" in resume_fn
    assert "update_task_status" not in resume_fn
    assert "skip_resume" in fn
    assert "→ failed" in fn


def test_chat_fast_path_excludes_fact_questions():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "_is_fact_q = is_fact_seeking_question(_user_msg_text)" in text
    # ruff format рвёт условие на строки — сверяем по нормализованному тексту
    flat = " ".join(text.split())
    assert "and not _is_fact_q" in flat
