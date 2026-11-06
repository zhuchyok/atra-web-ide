"""Open WebUI ask_victoria: библия = ATRA docs, context ≤128, без stub-fastpath."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIGS = os.path.join(ROOT, "configs")
if CONFIGS not in sys.path:
    sys.path.insert(0, CONFIGS)

import openwebui_ask_victoria_tool as tool  # noqa: E402


def test_force_bible_rewrites_plain_bible():
    out = tool._force_atra_bible_intent("покажи библию")
    assert "MASTER_REFERENCE.md" in out
    assert "религиозн" in out.lower()
    assert "покажи библию" in out


def test_force_bible_keeps_explicit_path():
    g = "прочитай docs/MASTER_REFERENCE.md раздел портов"
    assert tool._force_atra_bible_intent(g) == g


def test_sanitize_project_context_truncates():
    long = "x" * 200
    assert len(tool._sanitize_project_context(long)) == 128
    assert tool._sanitize_project_context("") == "atra-web-ide"
    assert tool._sanitize_project_context("  atra-web-ide  ") == "atra-web-ide"


def test_is_atra_bible_request():
    assert tool._is_atra_bible_request("покажи библию") is True
    assert tool._is_atra_bible_request("прочитай MASTER_REFERENCE") is True
    assert tool._is_atra_bible_request("столица Франции") is False


def test_no_local_bible_fastpath_skip():
    src = open(os.path.join(CONFIGS, "openwebui_ask_victoria_tool.py"), encoding="utf-8").read()
    assert "_local_bible_fastpath" not in src
    assert "_force_atra_bible_intent" in src
