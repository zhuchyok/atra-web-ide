"""Regression checks for truncated JSON handling and token limits in ReAct/expert flow."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REACT_AGENT = ROOT / "knowledge_os" / "app" / "react_agent.py"
EXPERT_WORKER = ROOT / "knowledge_os" / "app" / "expert_worker.py"


def test_react_has_truncated_json_repair_guard():
    text = REACT_AGENT.read_text(encoding="utf-8")
    assert "def _repair_truncated_json(raw: str) -> str:" in text
    assert "[PARSE-REPAIR]" in text
    assert "[PARSE-FALLBACK-LOOSE]" in text


def test_react_uses_stage_specific_token_limits():
    text = REACT_AGENT.read_text(encoding="utf-8")
    assert 'REACT_THINK_MAX_TOKENS", "4096"' in text
    assert 'REACT_ACT_MAX_TOKENS", "12288"' in text
    assert 'REACT_REFLECT_MAX_TOKENS", "2048"' in text
    assert "max_tokens: Optional[int] = None" in text
    assert 'REACT_NUM_PREDICT", "12288"' in text


def test_expert_dialogue_predict_limit_is_configurable():
    text = EXPERT_WORKER.read_text(encoding="utf-8")
    # v150.79: вызов os.getenv разложен форматтером по строкам — сверяем без учёта пробелов.
    assert 'EXPERT_DIALOGUE_NUM_PREDICT", "4096"' in " ".join(text.split())
