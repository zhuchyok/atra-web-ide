"""Day-better: OpenAI stream emits stage delta.content for long goals."""

from pathlib import Path

VS = Path(__file__).resolve().parents[2] / "src" / "agents" / "bridge" / "victoria_server.py"


def test_stream_stage_helpers_exist():
    text = VS.read_text(encoding="utf-8")
    assert "def _stream_stage_enabled" in text
    assert "def _stream_stage_label" in text
    assert "def _openai_sse_content_chunk" in text
    assert "def _iter_async_handoff_for_chat" in text
    assert 'VICTORIA_STREAM_STAGE"' in text or "VICTORIA_STREAM_STAGE" in text


def test_stream_generator_emits_stage_before_run_task():
    text = VS.read_text(encoding="utf-8")
    start = text.index("# --- РЕАЛИЗАЦИЯ СТРИМИНГА (OPENAI COMPATIBLE) ---")
    block = text[start : start + 12000]
    assert "_stage_on = _stream_stage_enabled() and not _is_simple" in block
    assert "_stream_stage_label(0.0)" in block
    assert "emit_stages=_stage_on" in block
    assert "Перехожу в фон" in block


def test_stream_stage_label_behavior():
    text = VS.read_text(encoding="utf-8")
    start = text.index("def _stream_stage_label")
    end = text.index("\ndef _openai_sse_content_chunk", start)
    helper = text[start:end]
    ns: dict = {}
    exec(helper, ns)  # noqa: S102
    fn = ns["_stream_stage_label"]
    assert "Начинаю" in fn(0.0)
    assert "Думаю" in fn(10.0)
    assert "стратегия" in fn(5.0, "strategy")
    assert fn(5.0, "strategy").endswith("\n")
