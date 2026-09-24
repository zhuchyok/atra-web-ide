"""Regression guards for cleaning transcript-like model tails in /run output."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"


def test_normalizer_has_transcript_tail_patterns():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "transcript_tail_patterns = (" in text
    assert r"\n##\s*query:\s*" in text
    assert r"\n##\s*response:\s*" in text
    assert r"\n\[[A-Za-zА-Яа-яЁё0-9_\- ]{2,30}\]:\s*(?:\n|$)" in text


def test_normalizer_trims_transcript_tail_before_return():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "cut_positions = []" in text
    assert "trimmed = s[: min(cut_positions)].rstrip()" in text
    assert "if trimmed:" in text
    assert "s = trimmed" in text


def test_normalizer_trims_short_latin_artifact_before_code_block():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert 'first_fence = s.find("```")' in text
    assert 're.fullmatch(r"[-A-Za-z0-9_,.!?\\"\'` ]+", prefix)' in text
    assert "and prefix.endswith(\".\")" in text
    assert "and \":\" not in prefix" in text
    assert "and len(prefix.split()) <= 3" in text
    assert 's = s[first_fence:].lstrip()' in text
