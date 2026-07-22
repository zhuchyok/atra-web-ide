import hashlib
import json
import os
import random
import re
from dataclasses import dataclass
from typing import Optional

from app.ingestion.judge import IngestionJudge


@dataclass
class GateDecision:
    decision: str  # accept|reject|borderline
    reason: str
    quality_score: float


class IngestionQualityGate:
    PROMPT_PATTERNS = (
        r"\brole\s*:",
        r"\btone\s*:",
        r"\bstrategy\s*:",
        r"\breturn\s+json\b",
        r"```",
        r"\bты\s*-\s*",
        r"\bверховный\b",
    )

    def __init__(self, judge: Optional[IngestionJudge] = None):
        self.min_len = int(os.getenv("INGESTION_GATE_MIN_LEN", "40"))
        self.max_len = int(os.getenv("INGESTION_GATE_MAX_LEN", "4000"))
        self.shadow_mode = os.getenv("INGESTION_GATE_SHADOW_MODE", "true").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        self.enforce_percent = max(
            0, min(100, int(os.getenv("INGESTION_GATE_ENFORCE_PERCENT", "0")))
        )
        self.judge = judge or IngestionJudge()

    def evaluate(self, text: str, source_type: str) -> GateDecision:
        cleaned = self._normalize(text)
        if self._has_prompt_artifact(cleaned):
            return GateDecision("reject", "prompt_artifact", 0.0)
        if len(cleaned) < self.min_len or len(cleaned) > self.max_len:
            return GateDecision("reject", "length_out_of_range", 0.0)
        if self._is_technical_noise(cleaned):
            return GateDecision("reject", "technical_noise", 0.0)
        if self._is_semantic_empty(cleaned):
            return GateDecision("reject", "semantic_empty", 0.1)
        if self._is_borderline(cleaned):
            return GateDecision("borderline", "needs_judge", 0.5)
        return GateDecision("accept", "deterministic_pass", 0.9)

    async def evaluate_async(self, text: str, source_type: str) -> GateDecision:
        base = self.evaluate(text, source_type)
        if base.decision != "borderline":
            return base

        judge_payload = await self.judge.evaluate(text, source_type)
        if not self._is_valid_judge_payload(judge_payload):
            return GateDecision("reject", "judge_invalid", 0.0)

        decision = judge_payload["decision"].strip().lower()
        if decision not in ("accept", "reject"):
            return GateDecision("reject", "judge_invalid_decision", 0.0)

        return GateDecision(
            decision=decision,
            reason=str(judge_payload["reason"]).strip() or "judge_decision",
            quality_score=float(judge_payload["quality_score"]),
        )

    def should_block(self, decision: GateDecision) -> bool:
        if decision.decision == "accept":
            return False
        if self.shadow_mode:
            return False
        return random.randint(1, 100) <= self.enforce_percent

    async def log_reject(
        self, conn, content: str, source_type: str, reason: str, gate_stage: str, metadata=None
    ):
        digest = hashlib.sha256((content or "").encode("utf-8")).hexdigest()
        payload = metadata or {}
        try:
            await conn.execute(
                """
                INSERT INTO knowledge_reject_log (candidate_hash, source_type, reject_reason, gate_stage, metadata)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                """,
                digest,
                source_type,
                reason,
                gate_stage,
                json.dumps(payload),
            )
            return True
        except Exception:
            return False

    def _normalize(self, text: str) -> str:
        txt = (text or "").strip()
        txt = re.sub(r"\s+", " ", txt)
        return txt

    def _has_prompt_artifact(self, text: str) -> bool:
        lower = text.lower()
        return any(re.search(p, lower) for p in self.PROMPT_PATTERNS)

    def _is_technical_noise(self, text: str) -> bool:
        lower = text.lower()
        noise_markers = (
            "traceback",
            "exception",
            "stack",
            "error:",
            "http/1.1",
            "docker",
            "postgresql://",
            # Agent/runtime dumps that must never enter research KB
            "ошибка парсинга ответа модели",
            "извините, сейчас я не могу",
            '{"action": "create_file"',
            '"action": "create_file"',
            "все источники недоступны",
        )
        return any(m in lower for m in noise_markers)

    def _is_semantic_empty(self, text: str) -> bool:
        # Low lexical diversity and excessive repetition usually indicates low value.
        words = re.findall(r"\w+", text.lower())
        if not words:
            return True
        unique_ratio = len(set(words)) / max(1, len(words))
        if unique_ratio < 0.2:
            return True
        filler_hits = sum(text.lower().count(k) for k in ("важно", "нужно", "сделать", "улучшить"))
        return filler_hits > max(10, len(words) // 4)

    def _is_borderline(self, text: str) -> bool:
        # Borderline if semi-structured, but not clearly bad or clearly high-value.
        lower = text.lower()
        has_fact_like = any(k in lower for k in ("because", "поэтому", "итог", "вывод", "result"))
        has_action_like = any(
            k in lower for k in ("run ", "выполнить", "шаг", "действие", "commit")
        )
        uncertainty_markers = ("частично", "неполно", "неясно", "сомнительно")
        if any(k in lower for k in uncertainty_markers):
            return True
        return has_fact_like ^ has_action_like

    def _is_valid_judge_payload(self, payload) -> bool:
        if not isinstance(payload, dict):
            return False
        required = {"decision", "reason", "quality_score"}
        if not required.issubset(payload.keys()):
            return False
        try:
            qs = float(payload["quality_score"])
        except (TypeError, ValueError):
            return False
        return 0.0 <= qs <= 1.0
