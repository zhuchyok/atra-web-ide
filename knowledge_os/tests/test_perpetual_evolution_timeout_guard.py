from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PERPETUAL_EVOLUTION = ROOT / "knowledge_os" / "app" / "perpetual_evolution.py"


def test_recursive_evolution_timeout_is_handled_as_budget_warning():
    text = PERPETUAL_EVOLUTION.read_text(encoding="utf-8")
    assert "except asyncio.TimeoutError:" in text
    assert "Recursive cycle timed out after %ss (budget mode)." in text
    assert "EVOLUTION_SCOUT_TIMEOUT_SEC" in text
