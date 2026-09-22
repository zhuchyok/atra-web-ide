"""Regression: the 2026-09-20 LOG_SCANNER sources must stay fixed."""

from pathlib import Path

from app.available_models_scanner import _skip_as_ollama_hands


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "knowledge_os" / "app"


def test_evolution_does_not_pass_model_kwarg():
    text = (APP / "recursive_evolution.py").read_text(encoding="utf-8")
    assert 'model="smollm2:360m"' not in text
    assert "run_smart_agent_async(prompt, expert_name=\"Даниил\")" in text


def test_asyncpg_interval_uses_bound_days():
    distill = (APP / "autonomous_distillation.py").read_text(encoding="utf-8")
    assert "INTERVAL '%s days'" not in distill
    assert "($2 * INTERVAL '1 day')" in distill

    for rel in (
        "load_predictor.py",
        "feedback_collector.py",
        "ml_router_ab_test.py",
        "medic/feedback_loop.py",
        "context_scaler.py",
    ):
        text = (APP / rel).read_text(encoding="utf-8")
        assert "INTERVAL '%s days'" not in text, rel
        assert "INTERVAL '1 day')" in text, rel


def test_sandbox_skips_pytest_when_missing():
    text = (APP / "quality_assurance.py").read_text(encoding="utf-8")
    assert 'if "import pytest" in combined_code:' in text
    assert "except ImportError:" in text


def test_distill_teacher_wisdom_remaps_to_phi():
    text = (APP / "distillation_engine.py").read_text(encoding="utf-8")
    assert 'if "wisdom" in str(model).lower():' in text
    assert 'model = "phi3.5:3.8b"' in text


def test_visual_search_embed_keeps_nomic_alive():
    text = (APP / "visual_search" / "search_engine_api.py").read_text(encoding="utf-8")
    assert '"keep_alive": -1' in text
    assert "timeout=60.0" in text


def test_react_and_worker_default_to_phi_hands():
    react = (APP / "react_agent.py").read_text(encoding="utf-8")
    assert 'model_name: str = "phi3.5:3.8b"' in react
    assert 'model_name: str = "victoria-wisdom-24k:latest"' not in react
    assert "_skip_as_ollama_hands(model)" in react
    worker = (APP / "expert_worker.py").read_text(encoding="utf-8")
    assert 'model_hint or "victoria-wisdom-24k:latest"' not in worker
    assert "if \"wisdom\" in str(react_model).lower():" in worker
    assert 'logger.error(f"🆔 [WORKER] I am identified as:' not in worker
    assert "Blackboard monitor started for %s" in worker


def test_inference_warmup_is_phi_not_lfm():
    text = (APP / "inference_optimizer.py").read_text(encoding="utf-8")
    assert 'lfm2.5-thinking:1.2b' not in text
    assert 'models_to_preload = ["phi3.5:3.8b"]' in text
    assert "logger.error" not in text


def test_wisdom_guard_pins_phi_after_unload():
    text = (ROOT / "scripts" / "ollama_wisdom_guard.py").read_text(encoding="utf-8")
    assert "def pin_phi():" in text
    assert "pinned phi3.5:3.8b" in text
    assert "def pin_nomic():" in text
    assert "11434 держит только phi3.5:3.8b и nomic" in text
    assert "def _enforce_hands_slot():" in text
    assert "urlopen(req, timeout=60)" in text


def test_corruption_probe_skips_hands_and_does_not_error_log():
    scanner = (APP / "available_models_scanner.py").read_text(encoding="utf-8")
    assert "if _skip_as_ollama_hands(m):" in scanner
    assert 'logger.error(f"🚨 [CORRUPTION]' not in scanner
    assert _skip_as_ollama_hands("victoria-wisdom-24k:latest")
    assert _skip_as_ollama_hands("deepseek-r1:32b")
    assert _skip_as_ollama_hands("minicpm-v:latest")
    assert not _skip_as_ollama_hands("phi3.5:3.8b")
