"""
Hybrid grounding for distilled wisdom (Singularity / RAGAS-inspired).

Layers:
  A) template / mode-collapse reject
  B) lexical token overlap (cheap faithfulness proxy)
  C) optional embedding cosine (semantic rescue)
"""

from __future__ import annotations

import math
import os
import re
from collections.abc import Iterable

# Known mode-collapse phrases observed in production redistill (victoria/phi).
_TEMPLATE_PHRASES = (
    "strategic imperative is to aggressively scale digital service",
    "aggressively scale digital service infrastructure",
    "scale digital service infrastructure in response",
    "digital service demand is expanding",
)

_STOP = frozenset(
    """
    a an the and or but if then else for to of in on at by with from as is are was were
    be been being this that these those it its they them their we our you your
    и или но если для на по из от до как это тот так же уже чем при
    """.split()
)

_TOKEN_RE = re.compile(r"[a-zа-яё0-9_]{4,}", re.IGNORECASE)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def tokenize(text: str) -> set[str]:
    if not text:
        return set()
    out: set[str] = set()
    for m in _TOKEN_RE.finditer(text.lower()):
        tok = m.group(0)
        if tok in _STOP:
            continue
        out.add(tok)
    return out


def is_template_spam(summary: str, instruction: str = "") -> bool:
    blob = f"{summary or ''} {instruction or ''}".lower()
    if not blob.strip():
        return True
    return any(p in blob for p in _TEMPLATE_PHRASES)


def lexical_overlap(source: str, claim: str) -> float:
    """Fraction of claim tokens supported by source (claim coverage)."""
    src = tokenize(source)
    clm = tokenize(claim)
    if not clm:
        return 0.0
    if not src:
        return 0.0
    hit = len(src & clm)
    return round(hit / max(1, len(clm)), 4)


def cosine_similarity(a: Iterable[float], b: Iterable[float]) -> float:
    va = list(a or [])
    vb = list(b or [])
    if not va or not vb or len(va) != len(vb):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(va, vb):
        fx = float(x)
        fy = float(y)
        dot += fx * fy
        na += fx * fx
        nb += fy * fy
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return round(dot / (math.sqrt(na) * math.sqrt(nb)), 4)


def check_grounding(
    source: str,
    wisdom_summary: str,
    instruction: str = "",
    *,
    embed_source: list[float] | None = None,
    embed_claim: list[float] | None = None,
) -> tuple[bool, float, str]:
    """
    Returns (ok, score, reason_pipe).
    Score in [0,1] for metadata; ok follows hybrid pass rule.
    """
    enabled = os.getenv("DISTILL_GROUNDING_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if not enabled:
        return True, 1.0, "grounding_disabled"

    reasons: list[str] = []
    summary = (wisdom_summary or "").strip()
    instr = (instruction or "").strip()
    claim = f"{summary} {instr}".strip()

    if is_template_spam(summary, instr):
        return False, 0.05, "template_spam"

    min_lex = _env_float("DISTILL_GROUNDING_MIN_LEXICAL", 0.12)
    min_emb = _env_float("DISTILL_GROUNDING_MIN_EMBED", 0.42)

    lex = lexical_overlap(source or "", claim)
    reasons.append(f"lexical={lex:.3f}")

    emb = 0.0
    emb_used = False
    if embed_source and embed_claim:
        emb = cosine_similarity(embed_source, embed_claim)
        emb_used = True
        reasons.append(f"embed={emb:.3f}")

    lex_ok = lex >= min_lex
    emb_ok = emb_used and emb >= min_emb

    if lex_ok:
        reasons.append("lexical_pass")
        score = min(1.0, 0.55 + lex)
        if emb_used:
            score = min(1.0, max(score, 0.50 + emb * 0.5))
        return True, round(score, 4), "|".join(reasons)

    if emb_ok:
        reasons.append("embed_rescue")
        return True, round(min(1.0, 0.50 + emb * 0.5), 4), "|".join(reasons)

    reasons.append("ungrounded")
    score = max(lex, emb * 0.5)
    return False, round(score, 4), "|".join(reasons)
