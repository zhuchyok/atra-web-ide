from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT = ROOT / "scripts" / "preflight_runtime_guard.py"


def test_preflight_treats_health_starting_as_not_ready_by_default():
    text = PREFLIGHT.read_text(encoding="utf-8")
    assert 'PREFLIGHT_ALLOW_HEALTH_STARTING' in text
    assert '"health: starting" in status_l' in text
    assert "ALLOW_HEALTH_STARTING or not is_starting" in text
    assert '"health_starting": is_starting' in text
