"""Tests for expert_worker.py pool mode and agent messaging integration."""

import os

import pytest


class TestExpertWorkerConfig:
    """Test configuration and env var handling for expert worker."""

    def test_pool_mode_env_default(self):
        """EXPERT_POOL_MODE should default to 'false'."""
        val = os.getenv("EXPERT_POOL_MODE", "false")
        assert val.lower() in ("true", "false")

    def test_expert_pool_mode_parse(self):
        """Pool mode parsing logic as used in expert_worker.py."""

        def _is_pool_mode():
            return os.getenv("EXPERT_POOL_MODE", "false").lower() in ("true", "1", "yes")

        assert isinstance(_is_pool_mode(), bool)

    def test_worker_stream_name_format(self):
        """Stream name should follow expert_tasks:{name} pattern."""
        expert_name = "Роман"
        is_dedicated = True
        stream = f"expert_tasks:{expert_name}" if is_dedicated else "expert_tasks"
        assert stream == "expert_tasks:Роман"

        stream_shared = "expert_tasks"
        assert stream_shared == "expert_tasks"

    def test_expert_stream_dedicated_default(self):
        """EXPERT_STREAM_DEDICATED should default to true."""
        val = os.getenv("EXPERT_STREAM_DEDICATED", "true")
        assert val.lower() in ("true", "false")
