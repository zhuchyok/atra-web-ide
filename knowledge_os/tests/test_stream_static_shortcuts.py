"""Day-better: stream OpenAI path must share static ≤2-word shortcuts with sync chat."""

from pathlib import Path

VS = Path(__file__).resolve().parents[2] / "src" / "agents" / "bridge" / "victoria_server.py"


def test_static_shortcut_helper_exists():
    text = VS.read_text(encoding="utf-8")
    assert "def _static_simple_shortcut_reply" in text
    start = text.index("def _static_simple_shortcut_reply")
    end = text.index("\ndef _force_deep_analysis_reason", start)
    block = text[start:end]
    assert 'return "Привет! Чем могу помочь?"' in block
    assert 'return "Чем могу помочь?"' in block
    assert "len(goal_lower.split()) <= 2" in block


def test_stream_path_uses_static_shortcut_before_run_task():
    text = VS.read_text(encoding="utf-8")
    chat = text.index('@app.post("/v1/chat/completions")')
    stream_fork = text.index("# --- РЕАЛИЗАЦИЯ СТРИМИНГА (OPENAI COMPATIBLE) ---", chat)
    # Shortcut gate must sit BEFORE the full stream generator that calls run_task.
    assert "_static_shortcut = _static_simple_shortcut_reply" in text[chat:stream_fork]
    assert (
        "if _static_shortcut and request.stream:" in text[chat:stream_fork]
        or "if _static_shortcut and request.stream:" in text[chat:stream_fork]
    )
    assert "openai_shortcut_stream_generator" in text[chat:stream_fork]
    assert "static shortcut (skip run_task)" in text[chat:stream_fork]
    # Full stream still exists after the shortcut early-return.
    assert "run_task(task_req, req, async_mode=False)" in text[stream_fork : stream_fork + 8000]


def test_static_shortcut_behavior_via_exec():
    """Light behavioral check without importing the full FastAPI app."""
    text = VS.read_text(encoding="utf-8")
    # Pull helper + minimal deps it needs from the same module source is brittle;
    # instead assert contract strings and exercise a copied predicate.
    start = text.index("def _static_simple_shortcut_reply")
    end = text.index("\ndef _force_deep_analysis_reason", start)
    helper_src = text[start:end]

    def is_fact_seeking_question(content: str) -> bool:
        return False

    from typing import Optional  # noqa: F401 — used by helper annotations

    ns: dict = {"Optional": Optional, "is_fact_seeking_question": is_fact_seeking_question}
    exec(helper_src, ns)  # noqa: S102 — test-only isolated exec of our own helper
    fn = ns["_static_simple_shortcut_reply"]
    assert fn("пинг") == "Чем могу помочь?"
    assert fn("привет") == "Привет! Чем могу помочь?"
    assert fn("кто ты") == "Да, я Виктория, Team Lead корпорации ATRA."
    assert fn("скажи одно слово") == "ок"
    assert fn("напиши подробный план миграции базы и деплоя") is None
