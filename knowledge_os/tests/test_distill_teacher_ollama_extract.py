"""Teacher Ollama extract: thinking-model empty response trap."""

import sys
from pathlib import Path

# app/ использует двойной импорт (from ollama_slot_pin / from app.ollama_slot_pin);
# в тестах нужен сам каталог app в sys.path, иначе v150.82 brain-pin импорт падает.
_APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from app.distillation_engine import KnowledgeDistiller


def test_extract_prefers_response():
    text = KnowledgeDistiller._extract_ollama_generate_text(
        {"response": '{"wisdom_summary":"a","instruction":"b","category":"ops"}', "thinking": "x"}
    )
    assert "wisdom_summary" in text
    assert text.startswith("{")


def test_extract_salvages_json_from_thinking():
    thinking = (
        "Here is my reasoning...\n"
        'Final: {"wisdom_summary":"Keep elite nodes deep","instruction":"Prefer strong teacher",'
        '"category":"strategy"}'
    )
    text = KnowledgeDistiller._extract_ollama_generate_text({"response": "", "thinking": thinking})
    assert '"wisdom_summary"' in text
    assert "Keep elite nodes deep" in text


def test_extract_empty_when_no_json_in_thinking():
    text = KnowledgeDistiller._extract_ollama_generate_text(
        {"response": "", "thinking": "Just rambling without JSON object"}
    )
    assert text == ""


def test_should_disable_thinking_for_victoria():
    assert KnowledgeDistiller._should_disable_thinking("victoria-wisdom-v3.5:latest")
    assert KnowledgeDistiller._should_disable_thinking("qwen3:8b")
    assert not KnowledgeDistiller._should_disable_thinking("phi3.5:3.8b")


def test_ollama_generate_body_sets_think_false_for_victoria():
    d = KnowledgeDistiller()
    # [v150] wisdom-модель в Ollama больше не существует: ремап на руки phi3.5
    # (контракт подтверждён test_distill_teacher_wisdom_remaps_to_phi) — think не нужен.
    body = d._ollama_generate_body("victoria-wisdom-v3.5:latest", "prompt")
    assert body["model"] == "phi3.5:3.8b"
    assert "think" not in body
    assert body["options"]["num_predict"] >= 128
    # Немапленная thinking-модель (qwen3) по-прежнему получает think=False.
    body_qwen = d._ollama_generate_body("qwen3:8b", "prompt")
    assert body_qwen.get("think") is False
    assert body_qwen["options"]["num_predict"] >= 128
    body_phi = d._ollama_generate_body("phi3.5:3.8b", "prompt")
    assert "think" not in body_phi


def test_quality_gate_full_signal_can_reach_high_band():
    score, reason = KnowledgeDistiller._compute_quality_gate(
        wisdom_summary="A" * 95,
        instruction="Apply this rule before delegating any mentorship note.",
        category="strategy",
        wisdom={},
    )
    assert score >= 0.8
    assert "full_signal_bonus" in reason


def test_ollama_is_busy_detects_503_and_pending():
    assert KnowledgeDistiller._ollama_is_busy(503, "")
    assert KnowledgeDistiller._ollama_is_busy(
        200, '{"error":"server busy, please try again. maximum pending requests exceeded"}'
    )
    assert not KnowledgeDistiller._ollama_is_busy(200, '{"response":"ok"}')
    assert not KnowledgeDistiller._ollama_is_busy(404, "model not found")
