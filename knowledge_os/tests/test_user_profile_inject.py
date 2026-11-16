"""Unit tests: Hermes-style USER.md profile inject helper."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.agents.bridge import user_profile as up  # noqa: E402


def test_load_user_profile_reads_file(tmp_path, monkeypatch):
    path = tmp_path / "USER.md"
    path.write_text(
        "# USER.md\n\n## Priorities\n- Speed\n\n## Preferences\n- Direct\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("VICTORIA_USER_PROFILE_PATH", str(path))
    text = up.load_user_profile(max_chars=1500)
    assert "Speed" in text
    assert "Direct" in text
    assert "USER.md" not in text  # banner stripped


def test_load_user_profile_truncates(tmp_path, monkeypatch):
    path = tmp_path / "USER.md"
    body = "## Other\n" + ("x" * 400) + "\n## Noise\n" + ("y" * 400)
    path.write_text(body, encoding="utf-8")
    monkeypatch.setenv("VICTORIA_USER_PROFILE_PATH", str(path))
    text = up.load_user_profile(max_chars=120)
    assert len(text) <= 120
    assert text  # non-empty


def test_load_user_profile_prefers_priority_sections_when_oversize(tmp_path, monkeypatch):
    path = tmp_path / "USER.md"
    path.write_text(
        "## Bio\n"
        + ("long fluff " * 80)
        + "\n## Текущие приоритеты\n1. Autonomy\n\n## Preferences\n- terse\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("VICTORIA_USER_PROFILE_PATH", str(path))
    # Oversize budget forces priority/preference section extract.
    text = up.load_user_profile(max_chars=200)
    assert "Autonomy" in text
    assert "terse" in text
    assert "long fluff" not in text


def test_flag_off_skips_inject(monkeypatch):
    monkeypatch.setenv("USER_PROFILE_INJECT", "false")
    assert up.user_profile_inject_enabled() is False
    # Callers skip format when flag off; helper still returns empty block for blank.
    assert up.format_user_profile_block("") == ""


def test_flag_default_on(monkeypatch):
    monkeypatch.delenv("USER_PROFILE_INJECT", raising=False)
    assert up.user_profile_inject_enabled() is True


def test_missing_file_ok(tmp_path, monkeypatch):
    missing = tmp_path / "nope" / "USER.md"
    monkeypatch.setenv("VICTORIA_USER_PROFILE_PATH", str(missing))
    assert up.load_user_profile() == ""


def test_format_user_profile_block_prefix():
    block = up.format_user_profile_block("Boss wants speed")
    assert block.startswith("\nUSER PROFILE (owner):\n")
    assert "Boss wants speed" in block


def test_victoria_server_wires_inject():
    """Source-level guard: project_prompt path calls USER profile inject."""
    server = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"
    text = server.read_text(encoding="utf-8")
    assert "load_user_profile" in text
    assert "USER_PROFILE_INJECT" in text or "user_profile_inject_enabled" in text
    assert "USER PROFILE (owner)" in text or "format_user_profile_block" in text
    inject_region = text.split("SESSION_INJECTION", 1)[1].split("БАЗА ЗНАНИЙ", 1)[0]
    assert "load_user_profile" in inject_region
    assert "format_user_profile_block" in inject_region
    # Path load targets USER.md only (no SOUL.md path reference in helper module)
    helper = (ROOT / "src" / "agents" / "bridge" / "user_profile.py").read_text(
        encoding="utf-8"
    )
    assert "USER.md" in helper
    assert 'SOUL.md"' not in helper and "SOUL.md'" not in helper
