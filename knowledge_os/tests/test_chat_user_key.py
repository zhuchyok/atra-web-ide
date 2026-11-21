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


def test_chat_path_no_ephemeral_openai_correlation_keys():
    """All four chat-path LTM/session sites must use resolved key, not openai-{uuid}."""
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    chat_start = text.index('@app.post("/v1/chat/completions")')
    # Chat handler ends at the next top-level route decorator after chat_completions.
    rest = text[chat_start + 1 :]
    next_route = rest.find("\n@app.")
    chat_region = text[chat_start : chat_start + 1 + next_route] if next_route != -1 else text[chat_start:]
    assert "openai-{correlation" not in chat_region
    assert "session_id=chat_user_key" in chat_region or "session_id=chat_user_key," in chat_region
    assert "user_key=chat_user_key" in chat_region
    assert "_resolve_chat_user_key" in chat_region
