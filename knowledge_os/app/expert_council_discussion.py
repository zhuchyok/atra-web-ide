# knowledge_os/app/expert_council_discussion.py
"""
[SINGULARITY 20.0] Expert Council Discussion (Brainstorming V2).
Autonomous multi-agent debate system with persistence in strategy_sessions.
"""

import asyncio
import json
import logging
import os
from datetime import datetime

import asyncpg
from ai_core import run_smart_agent_async
from expert_synthesizer import ExpertSynthesizer

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


class ExpertCouncil:
    def __init__(self, session_id=None):
        self.session_id = session_id
        self.base_experts = [
            {"name": "Игорь", "role": "backend_developer", "focus": "Architecture & Docker"},
            {"name": "Роман", "role": "database_engineer", "focus": "SQL & Migrations"},
            {"name": "Дмитрий", "role": "ml_engineer", "focus": "Ollama & MLX Performance"},
            {"name": "Анна", "role": "qa_engineer", "focus": "Testing & Reliability"},
            {"name": "Борис", "role": "devops_engineer", "focus": "Infrastructure, Docker, Deploy"},
            {"name": "Александр", "role": "security_architect", "focus": "Security, Audit"},
            {"name": "Евгения", "role": "marketing_director", "focus": "PR, Growth, Marketing"},
            {
                "name": "Константин",
                "role": "technical_lead",
                "focus": "Architecture, Technical Decisions",
            },
            {"name": "Артём", "role": "ux_ui_designer", "focus": "UX/UI Design, Web Strategy"},
        ]
        self.experts = self.base_experts.copy()

    async def start_debate(
        self, topic: str, initial_proposal: str, beautiful_mode: bool = True
    ) -> str:
        """
        Starts a multi-agent debate on a specific topic.
        [SINGULARITY 24.0] beautiful_mode is now TRUE by default.
        Includes Autonomous HR: Synthesizes a specialist if needed.
        """
        logger.info(f"🏛️ [COUNCIL] Starting debate on: {topic[:50]}...")

        try:
            conn = await asyncpg.connect(DB_URL)

            # [FIX] HR: Add existing expert from DB or synthesize new
            try:
                hr = ExpertSynthesizer()
                specialist = await hr.find_or_synthesize_expert(
                    f"ТЕМА: {topic}\nПРЕДЛОЖЕНИЕ: {initial_proposal}"
                )
                if specialist:
                    # Add existing OR new expert to council
                    if specialist.get("needs_new_expert"):
                        new_expert = {
                            "name": specialist.get("suggested_name"),
                            "role": specialist.get("suggested_role", "specialist"),
                            "focus": specialist.get("focus_area", ""),
                        }
                    elif specialist.get("existing"):
                        new_expert = {
                            "name": specialist.get("suggested_name"),
                            "role": specialist.get("suggested_role", "specialist"),
                            "focus": specialist.get("focus_area", ""),
                        }
                    else:
                        new_expert = None

                    if new_expert and new_expert not in self.experts and len(self.experts) < 12:
                        self.experts.append(new_expert)
                        source = "existing" if specialist.get("existing") else "synthesized"
                        logger.info(f"🧬 [COUNCIL] Added {source} specialist: {new_expert['name']}")
            except Exception as hre:
                logger.debug(f"HR synthesis skipped: {hre}")

            # 1. Create session if not exists
            if not self.session_id:
                self.session_id = await conn.fetchval(
                    """
                    INSERT INTO strategy_sessions (title, metadata)
                    VALUES ($1, $2) RETURNING id
                """,
                    f"Дебаты: {topic[:50]}",
                    json.dumps({"topic": topic, "initial_proposal": initial_proposal}),
                )

            debate_history = (
                f"ТЕМА: {topic}\nПРЕДЛОЖЕНИЕ: {initial_proposal}\n\n--- ХОД ДЕБАТОВ ---\n"
            )

            # 2. Sequential expert opinions
            for expert in self.experts:
                logger.info(f"🗣️ [COUNCIL] Calling expert: {expert['name']} ({expert['role']})")

                if beautiful_mode:
                    # [SINGULARITY 24.0] Immersive dialogue generation using TEAM_PERSONALITIES.md
                    prompt = f"""
                    ТЫ - {expert["name"]}, эксперт в области {expert["focus"]}.
                    ИДЕТ СОВЕТ ЭКСПЕРТОВ КОРПОРАЦИИ.

                    ИСПОЛЬЗУЙ СВОЙ ХАРАКТЕР ИЗ TEAM_PERSONALITIES.md:
                    - Стиль общения, ключевые фразы, эмодзи.
                    - Твоя роль: {expert["role"]}.

                    ТЕМА: {topic}
                    ТЕКУЩЕЕ ПРЕДЛОЖЕНИЕ: {initial_proposal}
                    ИСТОРИЯ ДЕБАТОВ:
                    {debate_history}

                    ЗАДАЧА: Выскажи свое мнение. Будь живым персонажем, как в реальном чате.
                    Найди слабые места или предложи улучшения.
                    ОТВЕТЬ КРАТКО (1-3 предложения), сохранив стиль.
                    """
                else:
                    prompt = f"""
                    ТЫ - {expert["name"]}, эксперт в области {expert["focus"]}.
                    ИДЕТ СОВЕТ ЭКСПЕРТОВ КОРПОРАЦИИ.

                    ТЕМА: {topic}
                    ТЕКУЩЕЕ ПРЕДЛОЖЕНИЕ: {initial_proposal}
                    ИСТОРИЯ ДЕБАТОВ:
                    {debate_history}

                    ЗАДАЧА: Проанализируй предложение со своей колокольни.
                    Найди слабые места, предложи улучшения или подтверди надежность.
                    Будь краток, профессионален и конструктивен.
                    """

                opinion = await asyncio.wait_for(
                    run_smart_agent_async(
                        prompt, expert_name=expert["name"], category="fast", is_vip=False
                    ),
                    timeout=60,
                )

                # Save to DB
                # Находим ID эксперта по имени
                expert_id_row = await conn.fetchrow(
                    "SELECT id FROM experts WHERE name = $1 LIMIT 1", expert["name"]
                )
                if expert_id_row:
                    # ВАЖНО: В БД expert_ids это UUID[], а не INTEGER[].
                    # Но в таблице experts поле id это INTEGER.
                    # Проверим тип поля expert_ids в expert_discussions.
                    # Судя по ошибке, там ожидается UUID[], но мы передаем INTEGER[].
                    # Однако в таблице experts id это INTEGER.
                    # Скорее всего, в expert_discussions expert_ids должен хранить UUID экспертов, если они есть.
                    # Но в нашей схеме эксперты имеют INTEGER id.
                    # Исправим запрос, чтобы он соответствовал схеме: используем явное приведение или проверим UUID.

                    # Попробуем найти UUID эксперта, если он есть в метаданных или другой колонке
                    # Если нет, просто приведем INTEGER к TEXT и потом к UUID (если это возможно)
                    # или исправим саму вставку.

                    await conn.execute(
                        """
                        INSERT INTO expert_discussions (session_id, topic, consensus_summary, status, metadata)
                        VALUES ($1, $2, $3, 'completed', $4::jsonb)
                    """,
                        self.session_id,
                        topic,
                        opinion,
                        json.dumps(
                            {"expert_name": expert["name"], "expert_id": str(expert_id_row["id"])}
                        ),
                    )

                debate_history += f"\n[{expert['name']}]: {opinion}\n"

            # 3. Final Synthesis by Victoria
            logger.info("👑 [COUNCIL] Victoria is synthesizing final decision...")
            if beautiful_mode:
                synthesis_prompt = f"""
                ТЫ - ВИКТОРИЯ, Team Lead.
                ПРОАНАЛИЗИРУЙ итоги дебатов экспертов и вынеси ФИНАЛЬНОЕ РЕШЕНИЕ.

                ИСПОЛЬЗУЙ СВОЙ ХАРАКТЕР ИЗ TEAM_PERSONALITIES.md:
                - Спокойный координатор, видит общую картину.
                - Используй эмодзи для структурирования.
                - Краткое резюме и четкий план.

                ТЕМА: {topic}
                ИТОГИ ДЕБАТОВ:
                {debate_history}

                ВЕРНИ КРАСИВОЕ ОБСУЖДЕНИЕ КОМАНДЫ И ФИНАЛЬНЫЙ ПЛАН ДЕЙСТВИЙ.
                """
            else:
                synthesis_prompt = f"""
                ТЫ - ВИКТОРИЯ, Team Lead.
                ПРОАНАЛИЗИРУЙ итоги дебатов экспертов и вынеси ФИНАЛЬНОЕ РЕШЕНИЕ.

                ТЕМА: {topic}
                ИТОГИ ДЕБАТОВ:
                {debate_history}

                ВЕРНИ ФИНАЛЬНЫЙ ПЛАН ДЕЙСТВИЙ.
                """
            try:
                final_decision = await asyncio.wait_for(
                    run_smart_agent_async(
                        synthesis_prompt, expert_name="Виктория", category="general", is_vip=False
                    ),
                    timeout=120,
                )
            except asyncio.TimeoutError:
                logger.warning("⚠️ [COUNCIL] Victoria synthesis timed out, saving partial results")
                final_decision = (
                    debate_history
                    + "\n\n[COUNCIL] Victoria synthesis timed out. Partial results above."
                )

            # Update session status
            await conn.execute(
                """
                UPDATE strategy_sessions
                SET status = 'completed',
                    metadata = metadata || jsonb_build_object('final_decision', $1)
                WHERE id = $2
            """,
                final_decision,
                self.session_id,
            )

            await conn.close()
            return final_decision

        except Exception as e:
            logger.error(f"❌ [COUNCIL] Error in debate: {e}")
            return f"Ошибка при проведении дебатов: {e}"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def test():
        council = ExpertCouncil()
        decision = await council.start_debate(
            "Внедрение Hierarchy of Reasoning",
            "Использовать phi3.5 для простых задач и qwen2.5 для сложных через LocalRouter.",
        )
        print(f"\n--- ФИНАЛЬНОЕ РЕШЕНИЕ ---\n{decision}")

    asyncio.run(test())
