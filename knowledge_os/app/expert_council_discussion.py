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
    def __init__(self, session_id=None, max_experts: int | None = None):
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
        # Cap for API SLA — full roster still available via COUNCIL_MAX_EXPERTS.
        cap = max_experts
        if cap is None:
            try:
                cap = int(os.getenv("COUNCIL_MAX_EXPERTS", "3"))
            except ValueError:
                cap = 3
        self.experts = self.base_experts.copy()[: max(2, cap)]

    async def start_debate(
        self, topic: str, initial_proposal: str, beautiful_mode: bool = True
    ) -> str:
        """
        Starts a multi-agent debate on a specific topic.
        [SINGULARITY 24.0] beautiful_mode is now TRUE by default.
        Includes Autonomous HR: Synthesizes a specialist if needed.
        """
        logger.info(f"🏛️ [COUNCIL] Starting debate on: {topic[:50]}...")

        persist_db = os.getenv("COUNCIL_PERSIST_DB", "false").lower() in ("1", "true", "yes")
        conn = None
        try:
            if persist_db:
                conn = await asyncpg.connect(DB_URL)

            # HR synthesis optional (off by default for API SLA).
            if os.getenv("COUNCIL_ENABLE_HR", "false").lower() in ("1", "true", "yes"):
                try:
                    hr = ExpertSynthesizer()
                    specialist = await hr.find_or_synthesize_expert(
                        f"ТЕМА: {topic}\nПРЕДЛОЖЕНИЕ: {initial_proposal}"
                    )
                    if specialist:
                        if specialist.get("needs_new_expert") or specialist.get("existing"):
                            new_expert = {
                                "name": specialist.get("suggested_name"),
                                "role": specialist.get("suggested_role", "specialist"),
                                "focus": specialist.get("focus_area", ""),
                            }
                        else:
                            new_expert = None
                        max_roster = max(2, int(os.getenv("COUNCIL_MAX_EXPERTS", "3")))
                        if (
                            new_expert
                            and new_expert not in self.experts
                            and len(self.experts) < max_roster
                        ):
                            self.experts.append(new_expert)
                            source = "existing" if specialist.get("existing") else "synthesized"
                            logger.info(
                                "🧬 [COUNCIL] Added %s specialist: %s",
                                source,
                                new_expert["name"],
                            )
                except Exception as hre:
                    logger.debug("HR synthesis skipped: %s", hre)

            # 1. Create session if not exists (optional persistence)
            if persist_db and conn and not self.session_id:
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
            opinions: list[dict] = []
            per_expert_timeout = float(os.getenv("COUNCIL_EXPERT_TIMEOUT_SEC", "18"))

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

                incomplete = False
                reason = "ok"
                try:
                    try:
                        from dialogue_llm import generate_dialogue, is_incomplete_text
                    except ImportError:
                        from knowledge_os.app.dialogue_llm import (
                            generate_dialogue,
                            is_incomplete_text,
                        )

                    gen = await asyncio.wait_for(
                        generate_dialogue(
                            prompt, expert_name=expert["name"], model_hint="fast"
                        ),
                        timeout=per_expert_timeout,
                    )
                    opinion = gen.text
                    incomplete = (not gen.ok) or is_incomplete_text(opinion)
                    reason = gen.reason if incomplete else "ok"
                except asyncio.TimeoutError:
                    opinion = (
                        f"[INCOMPLETE] [{expert['name']}] timeout — "
                        f"no fabricated opinion for role {expert['role']}."
                    )
                    incomplete, reason = True, "timeout"
                    logger.warning("Council expert timeout: %s", expert["name"])
                except Exception as op_err:
                    opinion = f"[INCOMPLETE] [{expert['name']}] error: {op_err}"
                    incomplete, reason = True, "error"
                    logger.warning("Council expert error %s: %s", expert["name"], op_err)

                if persist_db and conn and self.session_id:
                    try:
                        expert_id_row = await conn.fetchrow(
                            "SELECT id FROM experts WHERE name = $1 LIMIT 1", expert["name"]
                        )
                        if expert_id_row:
                            await conn.execute(
                                """
                                INSERT INTO expert_discussions
                                    (session_id, topic, consensus_summary, status, metadata)
                                VALUES ($1, $2, $3, 'completed', $4::jsonb)
                            """,
                                self.session_id,
                                topic,
                                opinion,
                                json.dumps(
                                    {
                                        "expert_name": expert["name"],
                                        "expert_id": str(expert_id_row["id"]),
                                    }
                                ),
                            )
                    except Exception as db_err:
                        logger.debug("Council persist opinion skipped: %s", db_err)

                debate_history += f"\n[{expert['name']}]: {opinion}\n"
                opinions.append(
                    {
                        "expert_name": expert["name"],
                        "opinion": str(opinion),
                        "round": 1,
                        "incomplete": incomplete,
                        "reason": reason,
                    }
                )

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
            synth_incomplete = False
            synth_reason = "ok"
            try:
                try:
                    from dialogue_llm import generate_dialogue, is_incomplete_text
                except ImportError:
                    from knowledge_os.app.dialogue_llm import (
                        generate_dialogue,
                        is_incomplete_text,
                    )

                syn_timeout = float(os.getenv("COUNCIL_SYNTHESIS_TIMEOUT_SEC", "18"))
                gen = await asyncio.wait_for(
                    generate_dialogue(
                        synthesis_prompt, expert_name="Виктория", model_hint="fast"
                    ),
                    timeout=syn_timeout,
                )
                final_decision = gen.text
                if (not gen.ok) or is_incomplete_text(final_decision):
                    names = ", ".join(e["name"] for e in self.experts)
                    final_decision = (
                        f"[INCOMPLETE] Частичный итог совета ({names}): синтез не завершён. "
                        f"Тема: {topic}. Не заявлять сильный консенсус."
                    )
                    synth_incomplete, synth_reason = True, gen.reason or "synthesis_incomplete"
            except asyncio.TimeoutError:
                logger.warning("⚠️ [COUNCIL] Victoria synthesis timed out, saving partial results")
                final_decision = (
                    "[INCOMPLETE] [COUNCIL] Victoria synthesis timed out.\n" + debate_history
                )
                synth_incomplete, synth_reason = True, "timeout"
            except Exception as syn_err:
                logger.warning("Council synthesis error: %s", syn_err)
                final_decision = f"[INCOMPLETE] [COUNCIL] Synthesis error: {syn_err}"
                synth_incomplete, synth_reason = True, "error"

            if persist_db and conn and self.session_id:
                try:
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
                except Exception as db_err:
                    logger.debug("Council persist session skipped: %s", db_err)

            if conn:
                await conn.close()
            incomplete_n = sum(1 for o in opinions if o.get("incomplete"))
            quality_degraded = incomplete_n > 0 or synth_incomplete
            reasons = sorted(
                {
                    str(o.get("reason") or "")
                    for o in opinions
                    if o.get("incomplete") and o.get("reason")
                }
            )
            if synth_incomplete and synth_reason:
                reasons.append(synth_reason)
            score = 0.85 if opinions and not quality_degraded else 0.6
            if incomplete_n >= 2:
                score = min(score, 0.45)
            return {
                "topic": topic,
                "final_decision": final_decision,
                "debate_history": debate_history,
                "consensus_score": score,
                "participants": [e["name"] for e in self.experts],
                "opinions": opinions,
                "engine_used": "council",
                "quality_degraded": quality_degraded,
                "degraded_reason": ",".join(r for r in reasons if r),
            }

        except Exception as e:
            logger.error(f"❌ [COUNCIL] Error in debate: {e}")
            if conn:
                try:
                    await conn.close()
                except Exception:
                    pass
            return {
                "error": f"Ошибка при проведении дебатов: {e}",
                "final_decision": f"Ошибка при проведении дебатов: {e}",
                "engine_used": "council",
            }


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
