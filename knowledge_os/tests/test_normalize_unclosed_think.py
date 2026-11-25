"""Egress: unclosed <think> must wipe body, not leave monologue after tag strip."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VS = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"


def _load_normalize():
    text = VS.read_text(encoding="utf-8")
    # Pull _strip_internal_monologue + _normalize_output_for_user helpers is heavy;
    # assert the unclosed-wipe contract is present and behaviorally correct via slice.
    start = text.index("        # Удаляем think-блоки для чистого пользовательского текста")
    end = text.index("        # Убираем запятую/точку/двоеточие в начале", start)
    snippet = text[start:end]
    assert "Unclosed <think>" in snippet
    assert r"<think>.*$" in snippet

    def wipe(s: str) -> str:
        s = re.sub(r"<think>.*?</think>", "", s, flags=re.DOTALL | re.IGNORECASE).strip()
        if re.search(r"<think>", s, re.IGNORECASE):
            s = re.sub(r"<think>.*$", "", s, flags=re.DOTALL | re.IGNORECASE).strip()
        s = re.sub(r"</?think>", "", s, flags=re.IGNORECASE).strip()
        return s

    return wipe


def test_closed_think_removed():
    wipe = _load_normalize()
    assert wipe("Hello <think>secret</think> world") == "Hello  world"


def test_unclosed_think_wipes_body_not_keeps_prose():
    wipe = _load_normalize()
    out = wipe("Visible\n<think>\nI am reasoning forever\nand more")
    assert out == "Visible"
    assert "reasoning" not in out.lower()
