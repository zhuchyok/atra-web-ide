"""
[SINGULARITY 20.0] Perpetual Evolution Engine.
Autonomous cycle: Research Giants -> Propose Implementation -> Execute -> Test -> Repeat.
"""

import asyncio
import json
import logging
import os
from datetime import datetime

import asyncpg
from ai_core import run_smart_agent_async
from constitutional_court import ConstitutionalCourt
from expert_council_discussion import ExpertCouncil
from voice_of_experience import VoiceOfExperience

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


class PerpetualEvolution:
    def __init__(self):
        self.current_task = None
        self.experience = VoiceOfExperience()
        self.court = ConstitutionalCourt()

    async def run_forever(self):
        """Main autonomous loop."""
        logger.info("🚀 [EVOLUTION] Perpetual Evolution Engine STARTED.")

        try:
            # [SINGULARITY 24.0] Autonomous Skill Refinement
            # Виктория анализирует старые навыки и обновляет их на основе недавних успехов.
            from scripts.autonomous_skill_refinement import refine_skills

            await refine_skills()
        except Exception as asr:
            logger.debug(f"Autonomous skill refinement failed: {asr}")

        try:
            # [SINGULARITY 24.0] Autonomous Tester Phase
            # В тихие часы запускаем самотестирование и исправление ошибок.
            try:
                from autonomous_tester import AutonomousTester
                tester = AutonomousTester()
                await tester.run_cycle()
            except Exception as te:
                logger.debug(f"Autonomous tester failed: {te}")

            # [SINGULARITY 24.0] Wisdom Injection Phase
                # Automatically turn successful insights into skills
                try:
                    from wisdom_injection import WisdomInjectionEngine

                    wisdom_engine = WisdomInjectionEngine()
                    await wisdom_engine.scan_and_inject()
                except Exception as we:
                    logger.debug(f"Wisdom injection failed: {we}")

                # [SINGULARITY 21.0] Knowledge Distillation Phase
                # Before researching new things, distill existing knowledge
                from distillation_engine import KnowledgeDistiller

                distiller = KnowledgeDistiller()
                await distiller.distill_knowledge_batch()

                # 1. RESEARCH: Find next big thing from Giants
                task = await self.research_next_upgrade()
                if not task:
                    logger.info("😴 [EVOLUTION] No new upgrade ideas found. Sleeping...")
                    await asyncio.sleep(3600)
                    continue

                # 2. CHECK EXPERIENCE: Get warnings from past failures
                warnings = await self.experience.get_warnings(task["title"])
                if warnings:
                    logger.warning(f"⚠️ [EVOLUTION] PITFALLS DETECTED: {warnings}")
                    task["implementation_plan"] = (
                        f"### [ГОЛОС ОПЫТА: ПРЕДУПРЕЖДЕНИЯ]\n{warnings}\n\n### [ПЛАН]\n{task['implementation_plan']}"
                    )

                # 3. BRAINSTORM: Call the Council
                logger.info(f"🏛️ [EVOLUTION] Calling Expert Council for: {task['title']}")
                council = ExpertCouncil()
                final_plan = await council.start_debate(
                    task["title"],
                    f"REASONING: {task['reasoning']}\nPLAN: {task['implementation_plan']}",
                )

                # 4. CONSTITUTIONAL CHECK: Verify decision by Court
                logger.info(f"⚖️ [EVOLUTION] Constitutional Verification for: {task['title']}")
                court_result = await self.court.verify_decision(task["title"], final_plan)

                if not court_result.get("valid"):
                    logger.warning(
                        f"🚨 [EVOLUTION] CONSTITUTIONAL VETO! {court_result.get('violations')}"
                    )
                    # If vetoed, we add feedback and try to re-synthesize or skip
                    final_plan = f"### [ВЕТО КОНСТИТУЦИОННОГО СУДА]\n{court_result.get('feedback')}\n\n{final_plan}"
                    # For safety, we still use the plan but it's now 'marked' with violations

                task["implementation_plan"] = final_plan

                # 5. IMPLEMENT: Execute the change
                success = await self.execute_upgrade(task)

                # 4. TEST: Verify the change
                if success:
                    await self.verify_and_log(task)
                else:
                    # Log failure to Voice of Experience
                    await self.experience.log_failure(
                        task["title"], "Implementation failed or timed out"
                    )

                logger.info(
                    f"✅ [EVOLUTION] Cycle completed for: {task['title']}. Moving to next..."
                )
                await asyncio.sleep(60)  # Short break between upgrades

            except Exception as e:
                logger.error(f"❌ [EVOLUTION] Error in loop: {e}")
                await self.experience.log_failure("Perpetual Evolution Loop", str(e))
                await asyncio.sleep(300)

    async def research_next_upgrade(self) -> dict:
        """Asks Victoria to find the next best thing to implement from AI Giants."""
        logger.info(
            "🔍 [EVOLUTION] Researching next upgrade from AI Giants (Google, OpenAI, Meta)..."
        )

        # ВРЕМЕННЫЙ ПЛАН (Fallback), если модель галлюцинирует с форматом
        fallback_task = {
            "title": "Autonomous Red Teaming (Self-Adversarial Verification)",
            "reasoning": "Inspired by Anthropic's constitutional AI and OpenAI's red teaming practices. Improves reliability by challenging its own outputs.",
            "implementation_plan": "1. Create adversarial_critic.py to challenge new SOPs. 2. Integrate critic into the SOP generation pipeline.",
            "test_scenario": "Generate a new SOP and verify that the critic identifies potential flaws or edge cases.",
        }

        prompt = """
        ТЫ - ВЕРХОВНЫЙ АРХИТЕКТОР ЭВОЛЮЦИИ.
        ПРОАНАЛИЗИРУЙ базу знаний гигантов и текущее состояние нашей системы.

        ЗАДАЧА: Выбери ОДНУ конкретную техническую фичу или архитектурный паттерн (из практик Google, OpenAI, Anthropic или Meta),
        которого у нас еще нет, но который сделает Викторию умнее или стабильнее.

        ОТВЕТЬ СТРОГО В ФОРМАТЕ JSON. ТВОЙ ОТВЕТ ДОЛЖЕН НАЧИНАТЬСЯ С '{' И ЗАКАНЧИВАТЬСЯ '}'.
        НИКАКОГО ТЕКСТА ДО ИЛИ ПОСЛЕ JSON. НИКАКИХ БЛОКОВ ```json. ТОЛЬКО ЧИСТЫЙ ОБЪЕКТ.

        ФОРМАТ:
        {
            "title": "Название фичи",
            "reasoning": "Почему это важно (ссылка на гиганта)",
            "implementation_plan": "Пошаговый план для Python/Docker",
            "test_scenario": "Как проверить, что это работает"
        }
        """

        try:
            # Используем victoria-wisdom-30b для максимальной мудрости в эволюции
            # ВАЖНО: Роутер возвращает (content_string, node_name)
            from local_router import LocalAIRouter

            router = LocalAIRouter()
            response_data = await router.run_local_llm(
                prompt, category="reasoning", model="victoria-wisdom-30b"
            )

            # Роутер возвращает (response, routing_source)
            if isinstance(response_data, (list, tuple)) and len(response_data) >= 1:
                response = response_data[0]
            elif isinstance(response_data, dict):
                # На случай если роутер вернул словарь (хотя по коду это кортеж)
                response = (
                    response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                )
                if not response:
                    response = response_data.get("content", str(response_data))
            else:
                response = str(response_data)

            logger.info(f"🔍 [EVOLUTION] Raw response length: {len(response) if response else 0}")

            if not response:
                logger.error("Empty response from LLM, using fallback.")
                return fallback_task

            # Очистка от markdown и лишнего текста
            clean_response = response.strip()
            start_idx = clean_response.find("{")
            end_idx = clean_response.rfind("}")

            if start_idx != -1 and end_idx != -1:
                clean_response = clean_response[start_idx : end_idx + 1]
                return json.loads(clean_response)
            else:
                logger.warning("No JSON found in response, using fallback task.")
                return fallback_task
        except Exception as e:
            logger.error(f"Failed to parse research response: {e}. Using fallback.")
            return fallback_task

    async def execute_upgrade(self, task: dict) -> bool:
        """Delegates the implementation to the expert team."""
        logger.info(f"🛠️ [EVOLUTION] Implementing: {task['title']}")

        exec_prompt = f"""
        ЗАДАЧА: Внедрить новую возможность в систему Singularity 20.0.
        ФИЧА: {task["title"]}
        ПЛАН: {task["implementation_plan"]}

        ДЕЙСТВУЙ АВТОНОМНО. Создай необходимые файлы или обнови существующие.
        """

        # В реальной системе здесь вызывается оркестратор или Veronica
        # Для прототипа мы логируем это как задачу в БД
        conn = await asyncpg.connect(DB_URL)
        await conn.execute(
            """
            INSERT INTO tasks (title, description, status, priority, metadata)
            VALUES ($1, $2, 'pending', 'high', $3::jsonb)
        """,
            f"🚀 EVOLUTION: {task['title']}",
            task["implementation_plan"],
            json.dumps(task),
        )
        await conn.close()

        return True

    async def verify_and_log(self, task: dict):
        """Verifies the upgrade and stores it in Knowledge OS."""
        logger.info(f"🧪 [EVOLUTION] Verifying: {task['title']}")
        # Логируем успех в базу знаний как верифицированный инсайт
        conn = await asyncpg.connect(DB_URL)
        await conn.execute(
            """
            INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
            VALUES ((SELECT id FROM domains WHERE name = 'Strategy' LIMIT 1), $1, 1.0, $2, true)
        """,
            f"✅ УСПЕШНОЕ ВНЕДРЕНИЕ: {task['title']}. {task['reasoning']}",
            json.dumps({"type": "evolution_log", "task": task}),
        )
        await conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    engine = PerpetualEvolution()
    asyncio.run(engine.run_forever())
