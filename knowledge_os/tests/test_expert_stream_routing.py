"""Tests for per-expert Redis stream routing."""

import os

import pytest
from app.expert_stream_routing import (
    SHARED_EXPERT_STREAM,
    dedicated_stream_for_expert,
    dispatch_stream_for_expert,
    resolve_push_stream,
    worker_stream_name,
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("EXPERT_STREAM_DEDICATED", raising=False)


def test_dedicated_stream_name():
    assert dedicated_stream_for_expert("Анна") == "expert_tasks:Анна"
    assert dedicated_stream_for_expert("  Victoria  ") == "expert_tasks:Victoria"


def test_dispatch_uses_dedicated_by_default(monkeypatch):
    monkeypatch.setenv("EXPERT_STREAM_DEDICATED", "true")
    assert dispatch_stream_for_expert("Анна") == "expert_tasks:Анна"


def test_dispatch_shared_when_disabled(monkeypatch):
    monkeypatch.setenv("EXPERT_STREAM_DEDICATED", "false")
    assert dispatch_stream_for_expert("Анна") == SHARED_EXPERT_STREAM


def test_worker_stream_matches_expert(monkeypatch):
    monkeypatch.setenv("EXPERT_STREAM_DEDICATED", "true")
    assert worker_stream_name("Роман") == "expert_tasks:Роман"


def test_resolve_push_stream_from_payload(monkeypatch):
    monkeypatch.setenv("EXPERT_STREAM_DEDICATED", "true")
    resolved = resolve_push_stream(
        SHARED_EXPERT_STREAM,
        {"expert_name": "Анна", "task_id": "abc"},
    )
    assert resolved == "expert_tasks:Анна"


def test_resolve_push_keeps_shared_without_expert(monkeypatch):
    monkeypatch.setenv("EXPERT_STREAM_DEDICATED", "true")
    resolved = resolve_push_stream(SHARED_EXPERT_STREAM, {"task_id": "abc"})
    assert resolved == SHARED_EXPERT_STREAM
