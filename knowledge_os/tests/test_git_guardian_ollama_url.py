"""git_guardian: prefer OLLAMA_GUARDIAN_URL over brain 11434 when set."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"


def test_git_guardian_prefers_guardian_url(monkeypatch):
    monkeypatch.setenv("OLLAMA_GUARDIAN_URL", "http://127.0.0.1:11499")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    sys.path.insert(0, str(SCRIPTS))
    if "git_guardian" in sys.modules:
        del sys.modules["git_guardian"]
    import git_guardian  # noqa: F401

    importlib.reload(sys.modules["git_guardian"])
    assert sys.modules["git_guardian"].os.environ["OLLAMA_BASE_URL"] == "http://127.0.0.1:11499"
    assert sys.modules["git_guardian"].os.environ["OLLAMA_URL"] == "http://127.0.0.1:11499"


def test_git_guardian_source_documents_wisdom_guard_mitigation():
    text = (SCRIPTS / "git_guardian.py").read_text(encoding="utf-8")
    assert "OLLAMA_GUARDIAN_URL" in text
    assert "_should_unload" in text
