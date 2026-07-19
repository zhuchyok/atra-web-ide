"""
[SINGULARITY 10.0+] Multi-Agent Debate V2.
Orchestrates a debate between multiple expert models to reach an optimal solution for critical tasks.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ai_core import ContextSwapper, FactExtractor

logger = logging.getLogger(__name__)


@dataclass
class DebateParticipant:
    name: str
    model: str
    role: str


@dataclass
class DebateResult:
    topic: str
    final_decision: str
    consensus_score: float
    history: List[Dict[str, Any]]
    timestamp: datetime = datetime.now(timezone.utc)
    quality_degraded: bool = False
    degraded_reason: str = ""
    opinions: List[Dict[str, Any]] = None  # type: ignore[assignment]
    participants: List[str] = None  # type: ignore[assignment]
    engine_used: str = "debate"

    def __post_init__(self):
        if self.opinions is None:
            self.opinions = [
                {
                    "expert_name": str(h.get("expert") or ""),
                    "opinion": str(h.get("opinion") or ""),
                    "round": int(h.get("round") or 1),
                    "incomplete": bool(h.get("incomplete")),
                }
                for h in (self.history or [])
                if isinstance(h, dict)
            ]
        if self.participants is None:
            self.participants = sorted(
                {o["expert_name"] for o in self.opinions if o.get("expert_name")}
            )


class MultiAgentDebate:
    """
    Orchestrates a debate between different models/experts.
    """

    def __init__(self):
        # Default participants with different strengths
        # Prefer small always-resident models for API reliability.
        self.participants = [
            DebateParticipant(
                "Architect",
                "phi3.5:3.8b",
                "Focus on structure, scalability, and patterns.",
            ),
            DebateParticipant(
                "Security",
                "phi3.5:3.8b",
                "Focus on safety, vulnerabilities, and edge cases.",
            ),
            DebateParticipant(
                "Pragmatist",
                "phi3.5:3.8b",
                "Focus on simplicity, speed, and immediate results.",
            ),
        ]

    async def run_debate(
        self, topic: str, context: Optional[str] = None, rounds: int = 2
    ) -> DebateResult:
        """
        Run a multi-round debate on a specific topic.
        """
        logger.info(f"🗣️ [DEBATE] Starting debate on: {topic[:100]}...")

        history = []
        current_context = (context or "")[:3500]
        use_fact_extractor = os.getenv("DEBATE_USE_FACT_EXTRACTOR", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        extractor = FactExtractor() if use_fact_extractor else None
        if extractor and len(current_context) > 4000:
            logger.info("✂️ [DEBATE] Context too long, extracting facts...")
            current_context = await extractor.extract_facts(
                current_context, context_description="Debate initial context"
            )

        for r in range(1, rounds + 1):
            logger.info(f"🔄 [DEBATE] Round {r}/{rounds}")
            round_responses = []

            # Sequential opinions — avoids stampeding local Ollama under load.
            for p in self.participants:
                prompt = self._build_debate_prompt(p, topic, current_context, history, r)
                try:
                    opinion, incomplete, reason = await self._get_expert_opinion(p, prompt)
                except Exception as e:
                    opinion = f"[INCOMPLETE] [{p.name}] error: {e}"
                    incomplete, reason = True, "error"
                history.append(
                    {
                        "round": r,
                        "expert": p.name,
                        "opinion": str(opinion),
                        "incomplete": incomplete,
                        "reason": reason,
                    }
                )
                round_responses.append(f"[{p.name}]: {opinion}")

            # Update context for next round
            new_round_text = "\n\n" + "\n".join(round_responses)
            if extractor and len(current_context) + len(new_round_text) > 8000:
                logger.info(f"🔄 [DEBATE] Round {r} context too long, summarizing history...")
                round_summary = await extractor.extract_facts(
                    new_round_text, context_description=f"Debate round {r} summary"
                )
                current_context += f"\n\n### ROUND {r} SUMMARY:\n{round_summary}"
            else:
                current_context = (current_context + new_round_text)[-6000:]

        # Final synthesis by Victoria (Team Lead)
        final_decision, synth_incomplete, synth_reason = await self._synthesize_decision(
            topic, history
        )

        incomplete_n = sum(1 for h in history if h.get("incomplete"))
        quality_degraded = incomplete_n > 0 or synth_incomplete
        reasons = sorted(
            {
                str(h.get("reason") or "")
                for h in history
                if h.get("incomplete") and h.get("reason")
            }
        )
        if synth_incomplete and synth_reason:
            reasons.append(synth_reason)
        degraded_reason = ",".join(r for r in reasons if r) or (
            "partial_opinions" if quality_degraded else ""
        )

        # Calculate consensus score based on agreement (penalize incomplete)
        consensus_score = self._calculate_consensus(history)
        if quality_degraded:
            consensus_score = min(consensus_score, 0.45 if incomplete_n >= 2 else 0.6)

        return DebateResult(
            topic=topic,
            final_decision=final_decision,
            consensus_score=consensus_score,
            history=history,
            quality_degraded=quality_degraded,
            degraded_reason=degraded_reason,
            engine_used="debate",
        )

    def _build_debate_prompt(
        self,
        participant: DebateParticipant,
        topic: str,
        context: str,
        history: List[Dict],
        round_num: int,
    ) -> str:
        history_str = ""
        if history:
            history_str = "\n".join(
                [f"Round {h['round']} - {h['expert']}: {h['opinion']}" for h in history]
            )

        if round_num == 1:
            return f"""
You are the {participant.name}. {participant.role}
Topic for debate: {topic}
Context: {context}

Provide your initial expert opinion on how to solve this. Be concise but thorough.
"""
        else:
            return f"""
You are the {participant.name}. {participant.role}
Topic: {topic}
Previous rounds:
{history_str}

Analyze the opinions of other experts. Point out flaws in their logic or support good ideas.
Refine your own position to reach the best possible solution.
"""

    def _calculate_consensus(self, history: List[Dict[str, str]]) -> float:
        """Calculate consensus score based on debate history.

        Higher score = more agreement between experts.
        Based on keyword overlap and shared recommendations.
        """
        if not history:
            return 0.0

        # Get opinions from final round
        final_round = max(h["round"] for h in history)
        final_opinions = [h["opinion"].lower() for h in history if h["round"] == final_round]

        if len(final_opinions) < 2:
            return 0.5

        # Calculate word overlap between opinions
        all_words = set()
        for op in final_opinions:
            words = set(op.split())
            all_words.update(words)

        # Jaccard similarity between pairs
        similarities = []
        for i, op1 in enumerate(final_opinions):
            words1 = set(op1.split())
            for op2 in final_opinions[i + 1 :]:
                words2 = set(op2.split())
                if words1 or words2:
                    intersection = len(words1 & words2)
                    union = len(words1 | words2)
                    similarity = intersection / union if union > 0 else 0
                    similarities.append(similarity)

        if similarities:
            avg_similarity = sum(similarities) / len(similarities)
            # Scale to 0.5-1.0 range (even low similarity has some consensus)
            return 0.5 + (avg_similarity * 0.5)
        return 0.5

    async def _get_expert_opinion(
        self, participant: DebateParticipant, prompt: str
    ) -> tuple[str, bool, str]:
        try:
            try:
                from dialogue_llm import generate_dialogue, is_incomplete_text
            except ImportError:
                from knowledge_os.app.dialogue_llm import (
                    generate_dialogue,
                    is_incomplete_text,
                )

            result = await asyncio.wait_for(
                generate_dialogue(
                    prompt,
                    expert_name=participant.name,
                    model_hint=participant.model,
                ),
                timeout=float(os.getenv("DEBATE_EXPERT_TIMEOUT_SEC", "12")),
            )
            incomplete = (not result.ok) or is_incomplete_text(result.text)
            return result.text, incomplete, (result.reason if incomplete else "ok")
        except asyncio.TimeoutError:
            logger.warning("Debate expert %s timed out", participant.name)
            return (
                f"[INCOMPLETE] [{participant.name}] local model did not finish in time; "
                f"no fabricated opinion (role: {participant.role}).",
                True,
                "timeout",
            )
        except Exception as e:
            logger.warning("Debate expert %s dialogue_llm failed: %s", participant.name, e)
            return (
                f"[INCOMPLETE] [{participant.name}] local model incomplete; "
                f"no fabricated opinion (role: {participant.role}).",
                True,
                "error",
            )

    async def _synthesize_decision(
        self, topic: str, history: List[Dict]
    ) -> tuple[str, bool, str]:
        history_text = "\n".join([f"{h['expert']}: {h['opinion']}" for h in history])
        if len(history_text) > 5000:
            history_text = history_text[:5000]

        real_ops = [h for h in history if not h.get("incomplete")]
        if not real_ops:
            return (
                f"[INCOMPLETE] FINAL DECISION: no complete expert opinions for '{topic}'. "
                f"Do not treat as consensus. Reasons: "
                f"{','.join(sorted({str(h.get('reason') or 'unknown') for h in history}))}.",
                True,
                "no_complete_opinions",
            )

        synthesis_prompt = f"""
You are Victoria, Team Lead. You have listened to a debate between experts on the topic: {topic}

EXPERT OPINIONS (SUMMARIZED):
{history_text}

Based on the debate, provide the FINAL AUTHORITATIVE DECISION and implementation plan.
Select the best ideas and mitigate the risks mentioned. Be concise (max 12 sentences).
If some opinions are marked INCOMPLETE, do not invent their positions.
"""
        try:
            try:
                from dialogue_llm import generate_dialogue, is_incomplete_text
            except ImportError:
                from knowledge_os.app.dialogue_llm import (
                    generate_dialogue,
                    is_incomplete_text,
                )

            result = await asyncio.wait_for(
                generate_dialogue(
                    synthesis_prompt, expert_name="Виктория", model_hint="fast"
                ),
                timeout=float(os.getenv("DEBATE_SYNTHESIS_TIMEOUT_SEC", "20")),
            )
            if result.ok and not is_incomplete_text(result.text):
                return result.text, False, "ok"
        except Exception as e:
            logger.warning("Debate synthesis via dialogue_llm failed: %s", e)

        return (
            f"[INCOMPLETE] FINAL DECISION (partial): topic '{topic}'.\n"
            f"Use complete expert evidence below; do not treat as a strong unanimous vote.\n"
            f"Evidence:\n{history_text[:2500]}",
            True,
            "synthesis_incomplete",
        )


_instance = None


def get_multi_agent_debate():
    global _instance
    if _instance is None:
        _instance = MultiAgentDebate()
    return _instance
