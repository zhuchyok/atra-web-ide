import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from ollama_wisdom_guard import (
    _nomic_backoff_active,
    _should_pin_brain,
    _should_pin_nomic,
    _should_pin_phi,
    _should_pin_stable,
    _should_unload_coder,
)


def test_phi_and_brain_are_stray_on_coder_slot():
    assert _should_unload_coder("phi3.5:3.8b") is True
    assert _should_unload_coder("nomic-embed-text:latest") is True
    assert _should_unload_coder("victoria-qwen38:latest") is True


def test_coder_models_stay():
    assert _should_unload_coder("qwen3-coder:30b") is False
    assert _should_unload_coder("qwen2.5-coder:14b") is False


def test_pin_phi_skipped_when_any_phi_already_loaded():
    assert _should_pin_phi(["phi3.5:3.8b", "nomic-embed-text:latest"]) is False
    assert _should_pin_phi(["phi3.5:3.8b-stable"]) is False
    assert _should_pin_phi(["nomic-embed-text:latest"]) is True
    assert _should_pin_phi([]) is True


def test_pin_stable_skipped_when_base_phi_already_loaded():
    assert _should_pin_stable(["phi3.5:3.8b", "nomic-embed-text:latest"]) is False
    assert _should_pin_stable(["phi3.5:3.8b-stable", "nomic-embed-text:latest"]) is False


def test_pin_stable_only_when_hands_have_nomic_and_no_phi():
    assert _should_pin_stable(["nomic-embed-text:latest"]) is True
    assert _should_pin_stable([]) is False


def test_pin_brain_when_11434_empty():
    assert _should_pin_brain([]) is True
    assert _should_pin_brain(["phi3.5:3.8b"]) is True


def test_pin_brain_skipped_when_qwen38_loaded():
    assert _should_pin_brain(["victoria-qwen38:latest"]) is False
    assert _should_pin_brain(["qwen3.8:latest"]) is False


def test_brain_runner_alive_detects_blob(monkeypatch):
    import ollama_wisdom_guard as g

    monkeypatch.setattr(
        g.subprocess,
        "check_output",
        lambda *a, **k: "bikos 1 llama-server --model /Users/x/.ollama-brain/blobs/sha256-aa\n",
    )
    assert g._brain_runner_alive() is True
    monkeypatch.setattr(
        g.subprocess,
        "check_output",
        lambda *a, **k: "bikos 1 llama-server --model /Users/x/.ollama-hands-local/blobs/sha256-bb\n",
    )
    assert g._brain_runner_alive() is False


def test_pin_brain_ghost_does_not_generate():
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[2] / "scripts" / "ollama_wisdom_guard.py").read_text(
        encoding="utf-8"
    )
    brain_fn = src.split("def pin_brain():", 1)[1].split("def _should_unload(", 1)[0]
    assert "GHOST" in brain_fn
    assert "_brain_runner_alive" in brain_fn
    assert "kickstart only 11434" in brain_fn
    assert "would hang" in brain_fn


def test_pin_brain_keep_alive_is_duration_not_minus_one():
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[2] / "scripts" / "ollama_wisdom_guard.py").read_text(
        encoding="utf-8"
    )
    brain_fn = src.split("def pin_brain():", 1)[1].split("def _should_unload(", 1)[0]
    assert '"keep_alive": "24h"' in brain_fn
    assert '"keep_alive": -1' not in brain_fn


def test_pin_nomic_skipped_when_already_loaded():
    assert _should_pin_nomic(["phi3.5:3.8b", "nomic-embed-text:latest"]) is False
    assert _should_pin_nomic(["nomic-embed-text"]) is False


def test_pin_nomic_when_missing():
    assert _should_pin_nomic(["phi3.5:3.8b"]) is True
    assert _should_pin_nomic([]) is True


def test_pin_phi_ctx_leaves_room_for_nomic():
    import pathlib

    text = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "ollama_wisdom_guard.py"
    src = text.read_text(encoding="utf-8")
    assert '"num_ctx": 8192' in src
    assert '"num_ctx": 16384' not in src.split("def pin_nomic", 1)[0]


def test_runner_watchdog_brain_probe_uses_contract_ctx():
    import pathlib

    src = (
        pathlib.Path(__file__).resolve().parents[2] / "scripts" / "ollama_runner_watchdog.sh"
    ).read_text(encoding="utf-8")
    helper = src.split("probe_generate_payload()", 1)[1].split("brain_warmup_gate()", 1)[0]
    brain_branch = helper.split('port" = "11434"', 1)[1].split("else", 1)[0]
    assert '"num_ctx":16384' in brain_branch
    assert '"keep_alive":"24h"' in brain_branch
    assert "2048" not in brain_branch
    rest = src.replace(helper, "", 1)
    assert '"num_ctx":2048' not in rest
    assert rest.count("probe_generate_payload") >= 3


def test_launchd_canaries_use_contract_ctx():
    import pathlib

    src = (
        pathlib.Path(__file__).resolve().parents[2] / "scripts" / "launchd_watchdog.py"
    ).read_text(encoding="utf-8")
    brain = src.split("brain victoria-qwen38@11434", 1)[1][:500]
    assert '"num_ctx": 16384' in brain
    assert '"num_ctx": 2048' not in brain
    hands = src.split("hands phi3.5@11437", 1)[1].split("Brain canary", 1)[0]
    assert '"num_ctx": 8192' in hands
    assert '"num_ctx": 2048' not in hands


def test_worker_ops_are_info_not_error():
    import pathlib

    src = (
        pathlib.Path(__file__).resolve().parents[1] / "app" / "expert_worker.py"
    ).read_text(encoding="utf-8")
    assert 'logger.info("🏆 [AUCTION]' in src
    assert 'logger.error(f"🏆 [AUCTION]' not in src
    assert 'logger.info("🔄 [RESURRECTION] Found my task' in src
    assert 'logger.error(f"❌ [RESURRECTION] Recovery failed' in src


def test_nomic_backoff_after_fail():
    import ollama_wisdom_guard as g

    old_fail = g._PIN_NOMIC_FAIL_AT
    old_backoff = g._PIN_NOMIC_BACKOFF_SEC
    try:
        g._PIN_NOMIC_FAIL_AT = 1000.0
        g._PIN_NOMIC_BACKOFF_SEC = 900
        assert _nomic_backoff_active(now=1010.0) is True
        assert _nomic_backoff_active(now=1901.0) is False
    finally:
        g._PIN_NOMIC_FAIL_AT = old_fail
        g._PIN_NOMIC_BACKOFF_SEC = old_backoff


def test_adaptive_options_no_longer_hardcode_phi_16k():
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / "app" / "local_router.py").read_text(
        encoding="utf-8"
    )
    fn = src.split("def _get_adaptive_options", 1)[1].split("def _should_disable_thinking", 1)[0]
    assert "pinned_options" in fn
    assert 'options["num_ctx"] = 16384' not in fn
