"""Teacher Ollama extract: thinking-model empty response trap."""

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
    body = d._ollama_generate_body("victoria-wisdom-v3.5:latest", "prompt")
    assert body.get("think") is False
    assert body["options"]["num_predict"] >= 128
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
