"""v139: curiosity cooldown sees cancelled CB; timeout-cap keeps OK file-checks."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PHASES = ROOT / "knowledge_os" / "app" / "orchestrator_phases.py"
WORKER = ROOT / "knowledge_os" / "app" / "smart_worker_autonomous.py"


def test_curiosity_cooldown_includes_cancelled_circuit_breaker():
    text = PHASES.read_text(encoding="utf-8")
    start = text.index("recent_curiosity_failure = await conn.fetchval")
    chunk = text[start : start + 1200]
    assert "status IN ('failed', 'cancelled')" in chunk
    assert "circuit_breaker_loop_exhausted" in chunk
    assert "ILIKE '%Circuit Breaker%'" in chunk


def test_curiosity_global_cb_cooldown():
    text = PHASES.read_text(encoding="utf-8")
    assert "Curiosity global cooldown" in text
    assert "curiosity_engine_starvation" in text
    text = WORKER.read_text(encoding="utf-8")
    start = text.index("Kill zombie delegation tasks stuck in work_item_timeout")
    chunk = text[start : start + 1600]
    assert "!~* '^(ОК|OK)\\\\b'" in chunk or r"!~* '^(ОК|OK)\\b'" in chunk
    assert "completed_at IS NULL" in chunk
    assert "Delegation with OK result → completed" in text
