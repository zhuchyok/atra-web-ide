"""
[SINGULARITY 20.0] Collective Brainstorming Module.
Collaborative expert dialogue for design — API-hardened with dialogue_llm.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BrainstormingMessage:
    sender: str
    role: str
    content: str
    phase: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CollectiveBrainstorming:
    """
    Orchestrates a collaborative design process between AI experts.
    Fast API path: EXPLORATION + synthesis (default).
    Full path: EXPLORATION → CLARIFICATION → APPROACHES → design → plan.
    """

    def __init__(self, topic: str, context: Optional[str] = None):
        self.topic = topic
        self.initial_context = context or ""
        self.history: List[BrainstormingMessage] = []
        base_experts = [
            {
                "name": "Игорь",
                "role": "Backend & Infrastructure Architect",
                "focus": "scalability, database, security, performance",
            },
            {
                "name": "Анна",
                "role": "Frontend & UX Specialist",
                "focus": "user interaction, state management, Svelte, UI/UX",
            },
            {
                "name": "Елена",
                "role": "QA & Security Engineer",
                "focus": "testing, edge cases, vulnerabilities, stability",
            },
            {
                "name": "Дмитрий",
                "role": "ML & Embedding Specialist",
                "focus": "vector search, embeddings, model optimization, pgvector",
            },
        ]
        try:
            cap = max(2, int(os.getenv("BRAINSTORM_MAX_EXPERTS", "3")))
        except ValueError:
            cap = 3
        self.experts = base_experts[:cap]
        self.lead = {
            "name": "Виктория",
            "role": "Team Lead & Strategist",
            "focus": "coordination, alignment with goals, final decision",
        }
        self.per_call_timeout = float(os.getenv("BRAINSTORM_EXPERT_TIMEOUT_SEC", "90"))
        # Quality-local: full phases by default; set BRAINSTORM_FAST=true for UI smoke.
        self.fast_mode = os.getenv("BRAINSTORM_FAST", "false").lower() in ("1", "true", "yes")

    async def run_session(self) -> Dict[str, Any]:
        """Runs the brainstorming cycle and returns API-compatible payload."""
        logger.info(f"🧠 [BRAINSTORMING] Starting session on: {self.topic}")

        await self._run_phase(
            "EXPLORATION",
            "Проанализируйте задачу и дайте краткий комментарий со своей точки зрения (1-3 предложения).",
        )

        if not self.fast_mode:
            await self._run_phase(
                "CLARIFICATION",
                "Задайте один уточняющий вопрос коллегам (1 предложение).",
            )
            await self._run_phase(
                "APPROACHES",
                "Предложите 1-2 варианта реализации с плюсами/минусами (кратко).",
            )

        design = await self._synthesize_design()
        plan = (
            await self._create_implementation_plan(design)
            if not self.fast_mode
            else self._fast_plan(design)
        )

        try:
            from dialogue_llm import is_incomplete_text
        except ImportError:
            from knowledge_os.app.dialogue_llm import is_incomplete_text

        opinions = [
            {
                "expert_name": m.sender,
                "opinion": m.content,
                "round": 1,
                "phase": m.phase,
                "incomplete": is_incomplete_text(m.content),
            }
            for m in self.history
        ]
        final_decision = f"{design}\n\n---\n\n{plan}".strip()
        history_text = "\n".join(f"[{m.sender} ({m.phase})]: {m.content}" for m in self.history)
        incomplete_n = sum(1 for o in opinions if o.get("incomplete"))
        quality_degraded = incomplete_n > 0 or is_incomplete_text(final_decision)
        score = 0.8 if opinions and not quality_degraded else 0.55
        if incomplete_n >= 2:
            score = min(score, 0.45)

        return {
            "topic": self.topic,
            "design": design,
            "plan": plan,
            "dialogue": [m.__dict__ for m in self.history],
            "final_decision": final_decision,
            "debate_history": history_text,
            "participants": [e["name"] for e in self.experts] + [self.lead["name"]],
            "opinions": opinions,
            "consensus_score": score,
            "engine_used": "brainstorm",
            "quality_degraded": quality_degraded,
            "degraded_reason": "incomplete_opinions" if quality_degraded else "",
        }

    async def _run_phase(self, phase_name: str, phase_instruction: str):
        logger.info(f"🌀 [BRAINSTORMING] Phase: {phase_name}")

        tasks = [
            self._get_expert_response(
                expert,
                self._build_expert_prompt(expert, phase_name, phase_instruction),
                phase_name,
            )
            for expert in self.experts
        ]
        responses = await asyncio.gather(*tasks)
        for msg in responses:
            if msg:
                self.history.append(msg)

    def _build_expert_prompt(self, expert: Dict, phase: str, instruction: str) -> str:
        history_text = "\n".join(f"[{m.sender} ({m.role})]: {m.content}" for m in self.history)
        return f"""
ТЫ - {expert["name"]}, {expert["role"]}. Твой фокус: {expert["focus"]}.
МЫ НАХОДИМСЯ В ФАЗЕ: {phase}.

ЗАДАЧА: {self.topic}
ИСХОДНЫЙ КОНТЕКСТ: {self.initial_context}

ИСТОРИЯ ОБСУЖДЕНИЯ:
{history_text if history_text else "Обсуждение только началось."}

ИНСТРУКЦИЯ ДЛЯ ЭТОЙ ФАЗЫ:
{instruction}

ОТВЕТЬ КРАТКО И ПО СУЩЕСТВУ.
"""

    async def _llm(self, prompt: str, expert_name: str):
        try:
            from dialogue_llm import generate_dialogue
        except ImportError:
            from knowledge_os.app.dialogue_llm import generate_dialogue

        return await asyncio.wait_for(
            generate_dialogue(prompt, expert_name=expert_name, model_hint="fast"),
            timeout=self.per_call_timeout,
        )

    async def _get_expert_response(
        self, expert: Dict, prompt: str, phase: str
    ) -> Optional[BrainstormingMessage]:
        try:
            try:
                from dialogue_llm import is_incomplete_text
            except ImportError:
                from knowledge_os.app.dialogue_llm import is_incomplete_text

            gen = await self._llm(prompt, expert["name"])
            content = gen.text
            if (not gen.ok) or is_incomplete_text(content):
                content = (
                    f"[INCOMPLETE] [{expert['name']}] local model incomplete in phase {phase}; "
                    f"no fabricated opinion (focus: {expert['focus']})."
                )
            return BrainstormingMessage(
                sender=expert["name"], role=expert["role"], content=content, phase=phase
            )
        except Exception as e:
            logger.warning("Expert %s failed in phase %s: %s", expert["name"], phase, e)
            return BrainstormingMessage(
                sender=expert["name"],
                role=expert["role"],
                content=(
                    f"[INCOMPLETE] [{expert['name']}] local model incomplete in phase {phase}; "
                    f"no fabricated opinion."
                ),
                phase=phase,
            )

    async def _synthesize_design(self) -> str:
        logger.info("🏛️ [BRAINSTORMING] Synthesizing final design...")
        history_text = "\n".join(f"[{m.sender} ({m.role})]: {m.content}" for m in self.history)
        prompt = f"""
ТЫ - {self.lead["name"]}, {self.lead["role"]}.
Синтезируй краткий ТЕХНИЧЕСКИЙ ДИЗАЙН (5-8 пунктов) на основе обсуждения.

ЗАДАЧА: {self.topic}
ОБСУЖДЕНИЕ:
{history_text}

Включи: подход, компоненты, риски, критерий готовности.
"""
        try:
            design = await self._llm(prompt, self.lead["name"])
            if design and "временно недоступен" not in design:
                return design
        except Exception as e:
            logger.warning("Brainstorm design synthesis failed: %s", e)
        names = ", ".join(e["name"] for e in self.experts)
        return (
            f"Дизайн (синтез без LLM): тема «{self.topic}». "
            f"Участники: {names}. Подход: минимальный безопасный инкремент, "
            f"проверка рисков, затем расширение."
        )

    def _fast_plan(self, design: str) -> str:
        return (
            "План (fast):\n"
            "1. Зафиксировать scope и критерии успеха.\n"
            "2. Сделать минимальный прототип.\n"
            "3. Проверить риски (QA/Security).\n"
            "4. Расширить по результатам.\n\n"
            f"Опора на дизайн:\n{design[:500]}"
        )

    async def _create_implementation_plan(self, design: str) -> str:
        logger.info("📋 [BRAINSTORMING] Creating implementation plan...")
        prompt = f"""
ТЫ - {self.lead["name"]}, {self.lead["role"]}.
Создай краткий пошаговый ПЛАН РЕАЛИЗАЦИИ (этапы + критерии успеха).

ДИЗАЙН:
{design}
"""
        try:
            plan = await self._llm(prompt, self.lead["name"])
            if plan and "временно недоступен" not in plan:
                return plan
        except Exception as e:
            logger.warning("Brainstorm plan failed: %s", e)
        return self._fast_plan(design)


async def run_brainstorming(topic: str, context: Optional[str] = None):
    session = CollectiveBrainstorming(topic, context)
    result = await session.run_session()

    try:
        import aiofiles

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        safe_topic = "".join([c if c.isalnum() else "_" for c in topic[:30]])
        filename = f"docs/plans/BRAINSTORM_{timestamp}_{safe_topic}.md"
        os.makedirs("docs/plans", exist_ok=True)
        async with aiofiles.open(filename, "w", encoding="utf-8") as f:
            await f.write(f"# Brainstorming: {topic}\n\n")
            await f.write(f"## Final Design\n\n{result['design']}\n\n")
            await f.write(f"## Implementation Plan\n\n{result['plan']}\n\n")
            await f.write("## Dialogue History\n\n")
            for m in result["dialogue"]:
                await f.write(
                    f"### {m['sender']} ({m['role']}) - Phase: {m['phase']}\n{m['content']}\n\n"
                )
        logger.info("✅ [BRAINSTORMING COMPLETE] Result saved to %s", filename)
    except Exception as save_err:
        logger.debug("Brainstorm save skipped: %s", save_err)

    return result


if __name__ == "__main__":
    import sys

    topic = sys.argv[1] if len(sys.argv) > 1 else "Implement a new feature"
    asyncio.run(run_brainstorming(topic))
