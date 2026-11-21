"""Unit tests: chat user_key resolution priority for session memory."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"


def _load_resolve_chat_user_key():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    start = text.index("def _resolve_chat_user_key(")
    end = text.index("\n@app.post(\"/v1/chat/completions\")")
    ns: dict = {"os": os, "Optional": __import__("typing").Optional}
    # Minimal stand-ins so the annotated signature can exec.
    ns["ChatCompletionRequest"] = object
    ns["Request"] = object
    exec(compile(text[start:end], str(VICTORIA_SERVER), "exec"), ns)
    return ns["_resolve_chat_user_key"]


@pytest.fixture(scope="module")
def resolve_key():
    return _load_resolve_chat_user_key()


def _req(headers: dict | None = None):
    mock = MagicMock()
    mock.headers = headers or {}
    return mock


def test_header_x_victoria_user_wins(resolve_key, monkeypatch):
    monkeypatch.setenv("VICTORIA_CHAT_USER_KEY", "env-user")
    body = SimpleNamespace(user="body-user")
    assert resolve_key(body, _req({"X-Victoria-User": "hdr-victoria"})) == "hdr-victoria"


def test_header_x_session_id_wins_over_body(resolve_key, monkeypatch):
    monkeypatch.setenv("VICTORIA_CHAT_USER_KEY", "env-user")
    body = SimpleNamespace(user="body-user")
    assert resolve_key(body, _req({"X-Session-Id": "hdr-session"})) == "hdr-session"


def test_x_victoria_user_before_x_session_id(resolve_key, monkeypatch):
    monkeypatch.delenv("VICTORIA_CHAT_USER_KEY", raising=False)
    body = SimpleNamespace(user=None)
    assert (
        resolve_key(
            body,
            _req({"X-Victoria-User": "v-user", "X-Session-Id": "s-user"}),
        )
        == "v-user"
    )


def test_body_user_when_no_headers(resolve_key, monkeypatch):
    monkeypatch.setenv("VICTORIA_CHAT_USER_KEY", "env-user")
    body = SimpleNamespace(user="body-user")
    assert resolve_key(body, _req({})) == "body-user"


def test_env_when_no_header_or_body(resolve_key, monkeypatch):
    monkeypatch.setenv("VICTORIA_CHAT_USER_KEY", "env-user")
    body = SimpleNamespace(user=None)
    assert resolve_key(body, _req({})) == "env-user"


def test_empty_header_falls_through_to_body(resolve_key, monkeypatch):
    monkeypatch.delenv("VICTORIA_CHAT_USER_KEY", raising=False)
    body = SimpleNamespace(user="body-user")
    assert resolve_key(body, _req({"X-Victoria-User": "  "})) == "body-user"


def test_fallback_atra_default(resolve_key, monkeypatch):
    monkeypatch.delenv("VICTORIA_CHAT_USER_KEY", raising=False)
    body = SimpleNamespace(user=None)
    assert resolve_key(body, _req({})) == "atra-default"


def _chat_completions_region() -> str:
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    chat_start = text.index('@app.post("/v1/chat/completions")')
    # Chat handler ends at the next top-level route decorator after chat_completions.
    rest = text[chat_start + 1 :]
    next_route = rest.find("\n@app.")
    return text[chat_start : chat_start + 1 + next_route] if next_route != -1 else text[chat_start:]


def test_chat_path_no_ephemeral_openai_correlation_keys():
    """All four chat-path LTM/session sites must use resolved key, not openai-{uuid}."""
    chat_region = _chat_completions_region()
    assert "openai-{correlation" not in chat_region
    assert "session_id=chat_user_key" in chat_region or "session_id=chat_user_key," in chat_region
    assert "user_key=chat_user_key" in chat_region
    assert "_resolve_chat_user_key" in chat_region


def test_chat_path_injects_experience_lessons_after_live_fact():
    """Phase 2: non-simple chat LLM path calls _fetch_experience_lessons after live-fact."""
    chat_region = _chat_completions_region()
    live_fact_pos = chat_region.index("live_fact = await _build_live_fact_answer_for_run")
    # Early return on live_fact must precede experience inject.
    live_return_pos = chat_region.index("if live_fact:", live_fact_pos)
    exp_pos = chat_region.index("await _fetch_experience_lessons(")
    assert exp_pos > live_return_pos
    assert "ОПЫТ:" in chat_region
    # Same gate as LTM: only inside `if not _is_simple`.
    simple_gate = chat_region.index("if not _is_simple:")
    assert simple_gate < exp_pos
    # Cap / N=3 contract present in chat region.
    assert "_fetch_experience_lessons(exp_probe, 3)" in chat_region or (
        "_fetch_experience_lessons(" in chat_region and ", 3)" in chat_region[exp_pos : exp_pos + 80]
    )
