"""Wave A: conversational Q&A must not be treated as sync_safe-heavy."""

from pathlib import Path

VS = Path(__file__).resolve().parents[2] / "src" / "agents" / "bridge" / "victoria_server.py"


def test_conversational_markers_not_in_sync_safe_heavy_list():
    text = VS.read_text(encoding="utf-8")
    start = text.index("def _is_sync_safe_candidate")
    end = text.index("return len(low) <= 700", start)
    block = text[start:end]
    for bad in ('"объясни"', '"анализ"', '"почему"', '"сравни"', '"исследуй"', '"разбери"'):
        assert bad not in block, f"{bad} still excludes sync_safe"


def test_mutate_markers_still_present():
    text = VS.read_text(encoding="utf-8")
    start = text.index("def _is_sync_safe_candidate")
    end = text.index("return len(low) <= 700", start)
    block = text[start:end]
    for need in ('"создай файл"', '"deploy"', '"напиши код"', '".py"'):
        assert need in block


def test_request_async_preamble_always_skips():
    text = VS.read_text(encoding="utf-8")
    assert "Wave A: always skip wasted preamble on explicit async" in text
    # Old gated form should be gone
    assert 'request_async_mode" and (\n        _is_analysis_heavy_goal' not in text
