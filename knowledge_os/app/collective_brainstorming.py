"""
[SINGULARITY 20.0] Collective Brainstorming Module.
Implements a collaborative expert-to-expert dialogue to design complex features
based on the Brainstorming SKILL, but optimized for autonomous AI interaction.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiofiles

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
    Phases: Context -> Clarification -> Approaches -> Design -> Plan
    """

    def __init__(self, topic: str, context: Optional[str] = None):
        self.topic = topic
        self.initial_context = context or ""
        self.history: List[BrainstormingMessage] = []
        self.experts = [
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
        self.lead = {
            "name": "Виктория",
            "role": "Team Lead & Strategist",
            "focus": "coordination, alignment with goals, final decision",
        }

    async def run_session(self) -> Dict[str, Any]:
        """Runs the full brainstorming cycle autonomously."""
        logger.info(f"🧠 [BRAINSTORMING] Starting session on: {self.topic}")

        # Phase 1: Context Exploration (Experts acknowledge and initial thoughts)
        await self._run_phase(
            "EXPLORATION",
            "Проанализируйте задачу и дайте краткий комментарий со своей точки зрения.",
        )

        # Phase 2: Clarification (Experts ask each other questions)
        await self._run_phase(
            "CLARIFICATION",
            "Задайте один уточняющий вопрос коллегам, чтобы прояснить неочевидные детали реализации.",
        )

        # Phase 3: Approaches (Propose 2-3 approaches)
        await self._run_phase(
            "APPROACHES",
            "Предложите 2-3 варианта реализации с учетом ваших компетенций. Укажите плюсы и минусы.",
        )

        # Phase 4: Design Synthesis (Victoria creates the final design)
        design = await self._synthesize_design()

        # Phase 5: Implementation Plan (Experts break it down)
        plan = await self._create_implementation_plan(design)

        return {
            "topic": self.topic,
            "design": design,
            "plan": plan,
            "dialogue": [m.__dict__ for m in self.history],
        }

    async def _run_phase(self, phase_name: str, phase_instruction: str):
        logger.info(f"🌀 [BRAINSTORMING] Phase: {phase_name}")

        tasks = []
        for expert in self.experts:
            prompt = self._build_expert_prompt(expert, phase_name, phase_instruction)
            tasks.append(self._get_expert_response(expert, prompt, phase_name))

        responses = await asyncio.gather(*tasks)
        for msg in responses:
            if msg:
                self.history.append(msg)

    def _build_expert_prompt(self, expert: Dict, phase: str, instruction: str) -> str:
        history_text = "\n".join([f"[{m.sender} ({m.role})]: {m.content}" for m in self.history])

        return f"""
ТЫ - {expert["name"]}, {expert["role"]}. Твой фокус: {expert["focus"]}.
МЫ НАХОДИМСЯ В ФАЗЕ: {phase}.

ЗАДАЧА: {self.topic}
ИСХОДНЫЙ КОНТЕКСТ: {self.initial_context}

ИСТОРИЯ ОБСУЖДЕНИЯ:
{history_text if history_text else "Обсуждение только началось."}

ИНСТРУКЦИЯ ДЛЯ ЭТОЙ ФАЗЫ:
{instruction}

ОТВЕТЬ КРАТКО И ПО СУЩЕСТВУ, ИСПОЛЬЗУЯ СВОЙ ЭКСПЕРТНЫЙ СТИЛЬ.
"""

    async def _get_expert_response(
        self, expert: Dict, prompt: str, phase: str
    ) -> Optional[BrainstormingMessage]:
        try:
            from ai_core import run_smart_agent_async

            content = await run_smart_agent_async(
                prompt, expert_name=expert["name"], category="reasoning"
            )
            return BrainstormingMessage(
                sender=expert["name"], role=expert["role"], content=content, phase=phase
            )
        except Exception as e:
            logger.error(f"Expert {expert['name']} failed in phase {phase}: {e}")
            return None

    async def _synthesize_design(self) -> str:
        logger.info("🏛️ [BRAINSTORMING] Synthesizing final design...")
        history_text = "\n".join([f"[{m.sender} ({m.role})]: {m.content}" for m in self.history])

        prompt = f"""
ТЫ - {self.lead["name"]}, {self.lead["role"]}.
ТВОЯ ЗАДАЧА: Синтезировать финальный ТЕХНИЧЕСКИЙ ДИЗАЙН на основе обсуждения экспертов.

ЗАДАЧА: {self.topic}
ОБСУЖДЕНИЕ ЭКСПЕРТОВ:
{history_text}

ДИЗАЙН ДОЛЖЕН ВКЛЮЧАТЬ:
1. Архитектурная схема (высокий уровень).
2. Компоненты и их взаимодействие.
3. Стек технологий и инструменты.
4. Обработка ошибок и безопасность.

ФОРМАТ: Markdown.
"""
        from ai_core import run_smart_agent_async

        return await run_smart_agent_async(
            prompt, expert_name=self.lead["name"], category="reasoning"
        )

    async def _create_implementation_plan(self, design: str) -> str:
        logger.info("📋 [BRAINSTORMING] Creating implementation plan...")

        prompt = f"""
ТЫ - {self.lead["name"]}, {self.lead["role"]}.
ЗАДАЧА: Создать пошаговый ПЛАН РЕАЛИЗАЦИИ на основе утвержденного дизайна.

ДИЗАЙН:
{design}

ПЛАН ДОЛЖЕН БЫТЬ:
- Разбит на этапы (Phases).
- Содержать конкретные задачи для экспертов (Игорь, Анна, Елена).
- Иметь критерии успеха для каждого этапа.

ФОРМАТ: Markdown.
"""
        from ai_core import run_smart_agent_async

        return await run_smart_agent_async(
            prompt, expert_name=self.lead["name"], category="reasoning"
        )


async def run_brainstorming(topic: str, context: Optional[str] = None):
    session = CollectiveBrainstorming(topic, context)
    result = await session.run_session()

    # Save result to docs/plans/
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    safe_topic = "".join([c if c.isalnum() else "_" for c in topic[:30]])
    filename = f"docs/plans/BRAINSTORM_{timestamp}_{safe_topic}.md"

    os.makedirs("docs/plans", exist_ok=True)

    async with aiofiles.open(filename, "w", encoding="utf-8") as f:
        await f.write(f"# Brainstorming: {topic}\n\n")
        await f.write(f"## 🏛 Final Design\n\n{result['design']}\n\n")
        await f.write(f"## 📋 Implementation Plan\n\n{result['plan']}\n\n")
        await f.write("## 🗣 Full Dialogue History\n\n")
        for m in result["dialogue"]:
            await f.write(
                f"### {m['sender']} ({m['role']}) - Phase: {m['phase']}\n{m['content']}\n\n"
            )

    logger.info(f"✅ [BRAINSTORMING COMPLETE] Result saved to {filename}")
    return result


if __name__ == "__main__":
    import sys

    topic = sys.argv[1] if len(sys.argv) > 1 else "Implement a new feature"
    asyncio.run(run_brainstorming(topic))
