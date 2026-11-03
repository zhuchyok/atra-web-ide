import os
import sys

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if APP not in sys.path:
    sys.path.insert(0, APP)


def test_latest_does_not_handoff_to_anna():
    from explicit_handoffs import detect_deterministic_handoff, keyword_in_text

    assert keyword_in_text("victoria-qwen38:latest", "test") is False
    assert keyword_in_text("fastest path", "test") is False
    assert keyword_in_text("run pytest now", "pytest") is True
    assert keyword_in_text("нужен unit test", "unit test") is True
    assert detect_deterministic_handoff("Юлия", "keep_alive victoria-qwen38:latest", "") is None


def test_pytest_still_handoffs_to_anna():
    from explicit_handoffs import detect_deterministic_handoff

    h = detect_deterministic_handoff("Юлия", "прогони pytest по isolation", "")
    assert h is not None
    assert h.to_agent == "Анна"


def test_coder_solo_gate_blocks_phi_on_11436():
    from local_router import skip_hands_on_coder_slot, url_is_ollama

    assert url_is_ollama("http://host.docker.internal:11436") is True
    assert url_is_ollama("http://host.docker.internal:11437") is True
    assert skip_hands_on_coder_slot("http://host.docker.internal:11436", "phi3.5:3.8b") is True
    assert skip_hands_on_coder_slot("http://host.docker.internal:11436", "qwen3-coder:30b") is False
    assert skip_hands_on_coder_slot("http://host.docker.internal:11437", "phi3.5:3.8b") is False


def test_embed_fallback_default_excludes_coder():
    from semantic_cache import OLLAMA_EMBED_FALLBACK_URLS

    joined = ",".join(OLLAMA_EMBED_FALLBACK_URLS)
    assert "11436" not in joined
