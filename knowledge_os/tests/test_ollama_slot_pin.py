import os
import sys

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

from ollama_slot_pin import (
    fact_fast_track_slot,
    pinned_keep_alive,
    pinned_num_ctx,
    pinned_options,
)


def test_brain_ctx_and_keep_alive():
    assert pinned_num_ctx("victoria-qwen38:latest") == 16384
    assert pinned_keep_alive("victoria-qwen38:latest") == "24h"
    assert pinned_keep_alive("qwen3.8:latest") == "24h"


def test_fact_fast_track_uses_resident_phi_not_cold_stable():
    assert fact_fast_track_slot(["phi3.5:3.8b", "nomic-embed-text:latest"]) == (
        "phi3.5:3.8b",
        8192,
    )
    assert fact_fast_track_slot(["phi3.5:3.8b-stable", "nomic-embed-text:latest"]) == (
        "phi3.5:3.8b-stable",
        2048,
    )
    assert fact_fast_track_slot(["nomic-embed-text:latest"]) is None
    assert fact_fast_track_slot([]) is None


def test_phi_base_not_stable():
    assert pinned_num_ctx("phi3.5:3.8b") == 8192
    assert pinned_num_ctx("phi3.5:3.8b-stable") == 2048
    assert pinned_keep_alive("phi3.5:3.8b") == -1


def test_nomic_and_coder():
    assert pinned_num_ctx("nomic-embed-text:latest") == 2048
    assert pinned_num_ctx("qwen3-coder:30b") == 16384
    assert pinned_num_ctx("qwen2.5-coder:14b") == 16384


def test_extra_cannot_override_num_ctx():
    opts = pinned_options(
        "phi3.5:3.8b", extra={"num_ctx": 16384, "num_predict": 200, "temperature": 0.1}
    )
    assert opts["num_ctx"] == 8192
    assert opts["num_predict"] == 200
    assert opts["temperature"] == 0.1


def test_router_adaptive_uses_pin_not_16k_for_phi():
    from local_router import LocalAIRouter

    opts = LocalAIRouter._get_adaptive_options(
        LocalAIRouter.__new__(LocalAIRouter), "phi3.5:3.8b"
    )
    assert opts["num_ctx"] == 8192
    assert opts["num_predict"] == 1200


def test_router_brain_stays_16k():
    from local_router import LocalAIRouter

    opts = LocalAIRouter._get_adaptive_options(
        LocalAIRouter.__new__(LocalAIRouter), "victoria-qwen38:latest"
    )
    assert opts["num_ctx"] == 16384


def test_keep_alive_policy_brain_is_24h():
    from ollama_keep_alive_policy import get_keep_alive

    assert get_keep_alive("victoria-qwen38:latest", mlx_alive=True) == "24h"
    assert get_keep_alive("phi3.5:3.8b", mlx_alive=True) == -1


def test_brain_keep_alive_stays_24h_during_mlx_cooldown():
    import time

    import ollama_keep_alive_policy as policy
    from ollama_keep_alive_policy import get_keep_alive

    policy._last_mlx_failure_time = time.time()
    try:
        assert get_keep_alive("victoria-qwen38:latest", mlx_alive=True) == "24h"
    finally:
        policy._last_mlx_failure_time = 0.0


def test_worker_phi_call_sites_use_8192():
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / "app" / "expert_worker.py").read_text(
        encoding="utf-8"
    )
    fast = src.split("[FAST PATH] Ollama status", 1)[0][-2500:]
    assert "pinned_options(" in fast
    assert '"num_ctx": 4096' not in fast
    judge = src.split("JUDGE_GATE_TIMEOUT", 1)[1].split("return score", 1)[0]
    assert "pinned_options" in judge or '"num_ctx": 8192' in judge
    assert '"num_ctx": 4096' not in judge
