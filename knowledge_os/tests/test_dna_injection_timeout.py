"""DNA eval poll must wait Victoria TTC 420, not 180."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DNA = ROOT / "knowledge_os" / "app" / "expert_dna_wisdom_injection.py"


def test_dna_run_timeout_matches_victoria_ttc():
    text = DNA.read_text(encoding="utf-8")
    assert 'DNA_INJECTION_RUN_TIMEOUT", "420"' in text
    assert 'DNA_INJECTION_RUN_TIMEOUT", "180"' not in text
    skip = text.split("skipped_before_errors", 1)[1].split("inject_wisdom_dna", 1)[0]
    assert "logger.warning" in skip
    assert "logger.error" not in skip
