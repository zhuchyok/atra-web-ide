"""Hybrid distill grounding: template + lexical (+ embed rescue)."""

from app.distill_grounding import (
    check_grounding,
    cosine_similarity,
    is_template_spam,
    lexical_overlap,
)


def test_rejects_victoria_template_spam():
    source = "🏛 Консультация Совета: обрезанные результаты паттерна задач SLA"
    summary = (
        "The strategic imperative is to aggressively scale digital service "
        "infrastructure in response to accelerating demand."
    )
    ok, score, reason = check_grounding(source, summary, "Analyze capacity metrics")
    assert ok is False
    assert "template_spam" in reason
    assert score < 0.2


def test_accepts_grounded_mentorship_wisdom():
    source = (
        "🎓 MENTORSHIP NOTE for Олег: для задач вроде делегирования "
        "пиши measurable outcomes в tasks.result и не закрывай сервисы "
        "только по health-check."
    )
    summary = (
        "Maintain measurable outcomes in tasks.result and avoid closing "
        "services based only on health-check signals."
    )
    instruction = "Ensure result tracking without relying on health-check closure alone."
    ok, score, reason = check_grounding(source, summary, instruction)
    assert ok is True
    assert "lexical_pass" in reason
    assert score >= 0.5


def test_lexical_overlap_basic():
    assert lexical_overlap("alpha beta gamma delta", "gamma delta epsilon") >= 0.4
    assert lexical_overlap("aaaa bbbb", "zzzz yyyy") == 0.0


def test_template_helper():
    assert is_template_spam("Digital service demand is expanding.", "x" * 30)
    assert not is_template_spam(
        "Write measurable task results for delegated mentorship notes.",
        "Track outcomes in tasks.result before closing.",
    )


def test_embed_rescue_when_lexical_weak():
    # Artificial: weak lexical but high embed cosine → rescue
    src = "qwer asdf zxcv uiop hjkl"
    claim_sum = "mnop vbnm qazx wsde"
    # same vector → cosine 1.0
    vec = [0.1, 0.2, 0.3, 0.4]
    ok, score, reason = check_grounding(
        src,
        claim_sum,
        "more filler words here for length",
        embed_source=vec,
        embed_claim=vec,
    )
    assert ok is True
    assert "embed_rescue" in reason
    assert cosine_similarity(vec, vec) == 1.0
