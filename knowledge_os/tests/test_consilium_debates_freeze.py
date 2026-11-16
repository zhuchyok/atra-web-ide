"""p95 KISS: consilium debate stays off under HYPOTHESIS_DEBATES freeze."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"
COMPOSE = ROOT / "knowledge_os" / "docker-compose.agents.yml"


def test_consilium_requires_debates_enabled():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    block = text[
        text.index("# === CONSILIUM ROUTER") : text.index("# === /CONSILIUM ROUTER ===")
    ]
    assert 'HYPOTHESIS_DEBATES_ENABLED", "false"' in block
    assert "outcome=\"disabled\"" in block or 'outcome="disabled"' in block
    assert "elif consilium_category and _cons_routing and _debates_enabled:" in block
    assert 'mode": "debate"' in block


def test_compose_keeps_hypothesis_debates_false():
    text = COMPOSE.read_text(encoding="utf-8")
    assert 'HYPOTHESIS_DEBATES_ENABLED: "false"' in text


def test_compose_async_timeouts_quality_first():
    """Allow long thick /run; do not raise the SLA alert threshold (420)."""
    text = COMPOSE.read_text(encoding="utf-8")
    assert 'VICTORIA_ASYNC_WATCHDOG_SEC: "480"' in text
    assert 'VICTORIA_ASYNC_HARD_TIMEOUT_SEC: "900"' in text
    # Alert threshold lives elsewhere — compose must not invent a higher SLA.
    assert "VICTORIA_ASYNC_TTC_P95_THRESHOLD" not in text
    assert 'VICTORIA_ASYNC_HARD_TIMEOUT_SEC: "1200"' not in text
